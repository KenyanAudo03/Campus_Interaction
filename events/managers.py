# managers.py
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
import logging
from django.utils import timezone
from .models import Event, EventRegistration
from .utils import send_registration_email, send_promotion_email, clear_event_cache

# Configure logging
logger = logging.getLogger(__name__)

# Constants for cache keys
CACHE_KEYS = {
    'event_status': 'event_status_{event_id}',
    'registration_status': 'registration_status_{event_id}_{profile_id}',
    'event_stats': 'event_stats_{event_id}'
}

class RegistrationManager:
    def __init__(self, event, user):
        self.event = event
        self.user = user
        self.profile = user.profile

    @transaction.atomic
    def register(self):
        try:
            event = self._get_locked_event()
            existing_registration = self._get_existing_registration(event)
            
            if existing_registration:
                logger.warning(f"User {self.user.id} attempted to register again for event {event.id}")
                return {'success': False, 'error': 'Already registered for this event'}

            registration_status, waitlist_position = self._determine_registration_status(event)
            registration = self._create_registration(event, registration_status, waitlist_position)

            self._clear_event_cache()
            self._send_registration_email(registration)

            return {
                'success': True,
                'status': registration.status,
                'waitlist_position': registration.waitlist_position if registration_status == 'waitlist' else None
            }

        except Exception as e:
            logger.error(f"Registration failed for user {self.user.id}: {str(e)}")
            raise

    def _get_locked_event(self):
        return Event.objects.select_for_update().get(id=self.event.id)

    def _get_existing_registration(self, event):
        return EventRegistration.objects.filter(
            event=event,
            participant=self.profile,
            status__in=['registered', 'waitlist']
        ).first()

    def _determine_registration_status(self, event):
        registered_count = event.registrations.filter(status='registered').count()
        should_waitlist = event.max_participants and (event.max_participants - registered_count <= 0)
        registration_status = 'waitlist' if should_waitlist else 'registered'
        waitlist_position = EventRegistration.objects.filter(event=event, status='waitlist').count() + 1 if should_waitlist else None
        return registration_status, waitlist_position

    def _create_registration(self, event, status, waitlist_position):
        registration = EventRegistration.objects.create(
            event=event,
            participant=self.profile,
            name=f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username,
            email=self.user.email,
            status=status,
            registered_at=timezone.now(),
            waitlist_position=waitlist_position
        )
        return registration

    def _clear_event_cache(self):
        clear_event_cache(self.event, self.profile.id)

    def _send_registration_email(self, registration):
        try:
            send_registration_email(registration)
        except Exception as e:
            logger.error(f"Failed to send registration email: {str(e)}")


class WaitlistManager:
    def __init__(self, event):
        self.event = event

    @transaction.atomic
    def process_cancellation(self, cancelled_registration):
        try:
            event = self._get_locked_event()
            was_registered = cancelled_registration.status == 'registered'

            self._update_cancelled_registration(cancelled_registration)
            if was_registered:
                self._promote_next_in_line(event)

            self._reorder_waitlist()
            self._clear_event_cache()

            logger.info(f"Successfully processed cancellation for registration {cancelled_registration.id}")
            return {'success': True, 'message': 'Registration cancelled successfully'}

        except Exception as e:
            logger.error(f"Cancellation processing failed: {str(e)}")
            raise

    def _get_locked_event(self):
        return Event.objects.select_for_update().get(id=self.event.id)

    def _update_cancelled_registration(self, registration):
        registration.status = 'cancelled'
        registration.waitlist_position = None
        registration.save()

    def _promote_next_in_line(self, event):
        next_in_line = EventRegistration.objects.filter(event=event, status='waitlist').order_by('registered_at').first()
        if next_in_line:
            logger.info(f"Promoting user {next_in_line.participant.id} from waitlist for event {event.id}")
            self._promote_registration(next_in_line)

    def _promote_registration(self, registration):
        try:
            registration.status = 'registered'
            registration.waitlist_position = None
            registration.save()
            send_promotion_email(registration)
        except Exception as e:
            logger.error(f"Failed to promote registration {registration.id}: {str(e)}")
            raise

    def _reorder_waitlist(self):
        waitlist_registrations = EventRegistration.objects.filter(event=self.event, status='waitlist').order_by('registered_at')
        for index, registration in enumerate(waitlist_registrations):
            registration.waitlist_position = index + 1
            registration.save()

    def _clear_event_cache(self):
        clear_event_cache(self.event)

class RegistrationRateLimiter:
    def __init__(self, user_id, event_id):
        self.cache_key = f'registration_attempt_{user_id}_{event_id}'
        self.timeout = getattr(settings, 'REGISTRATION_RATE_LIMIT_SECONDS', 60)

    def check_rate_limit(self):
        if cache.get(self.cache_key):
            return False
        cache.set(self.cache_key, True, self.timeout)
        return True