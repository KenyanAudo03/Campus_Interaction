# managers.py
from django.db import transaction
from django.core.cache import cache
from django.conf import settings
import logging
from django.utils import timezone

# Import models (adjust the import path according to your project structure)
from .models import Event, EventRegistration
from .utils import send_registration_email, send_promotion_email

# Configure logging
logger = logging.getLogger(__name__)

class RegistrationManager:
    def __init__(self, event, user):
        self.event = event
        self.user = user
        self.profile = user.profile

    @transaction.atomic
    def register(self):
        try:
            # Lock the event for atomic operations
            event = Event.objects.select_for_update().get(id=self.event.id)
            
            # Check if already registered
            existing_registration = EventRegistration.objects.filter(
                event=event,
                participant=self.profile,
                status__in=['registered', 'waitlist']
            ).first()

            if existing_registration:
                logger.warning(
                    f"User {self.user.id} attempted to register again for event {event.id}"
                )
                return {
                    'success': False,
                    'error': 'Already registered for this event'
                }

            # Get current registration counts
            registered_count = event.registrations.filter(
                status='registered'
            ).count()
            
            # Determine if should go to waitlist
            should_waitlist = False
            if event.max_participants:
                spots_left = event.max_participants - registered_count
                should_waitlist = spots_left <= 0

            # Determine status
            registration_status = 'waitlist' if should_waitlist else 'registered'

            # Create registration
            registration = EventRegistration.objects.create(
                event=event,
                participant=self.profile,
                name=f"{self.user.first_name} {self.user.last_name}".strip() or self.user.username,
                email=self.user.email,
                status=registration_status,
                registered_at=timezone.now()
            )

            # If waitlisted, set position
            if registration_status == 'waitlist':
                waitlist_position = EventRegistration.objects.filter(
                    event=event,
                    status='waitlist'
                ).count()
                registration.waitlist_position = waitlist_position
                registration.save()

            # Clear related caches
            self._clear_event_cache()

            # Send appropriate email
            try:
                send_registration_email(registration)
            except Exception as e:
                logger.error(f"Failed to send registration email: {str(e)}")
                # Don't fail the registration if email fails

            logger.info(
                f"Successfully registered user {self.user.id} for event {event.id} "
                f"with status {registration_status}"
            )

            return {
                'success': True,
                'status': registration_status,
                'waitlist_position': registration.waitlist_position if should_waitlist else None
            }

        except Exception as e:
            logger.error(f"Registration failed for user {self.user.id}: {str(e)}")
            raise

    def _clear_event_cache(self):
        """Clear all related cache keys"""
        cache_keys = [
            f'event_status_{self.event.id}',
            f'registration_status_{self.event.id}_{self.profile.id}',
            f'event_stats_{self.event.id}'
        ]
        cache.delete_many(cache_keys)


class WaitlistManager:
    def __init__(self, event):
        self.event = event

    @transaction.atomic
    def process_cancellation(self, cancelled_registration):
        try:
            # Lock the event for atomic operations
            event = Event.objects.select_for_update().get(id=self.event.id)
            was_registered = cancelled_registration.status == 'registered'

            # Update the cancelled registration
            cancelled_registration.status = 'cancelled'
            cancelled_registration.waitlist_position = None
            cancelled_registration.save()

            # If was registered and there are waitlisted people, promote next in line
            if was_registered:
                next_in_line = EventRegistration.objects.filter(
                    event=event,
                    status='waitlist'
                ).order_by('registered_at').first()

                if next_in_line:
                    logger.info(
                        f"Promoting user {next_in_line.participant.id} from waitlist "
                        f"for event {event.id}"
                    )
                    self._promote_registration(next_in_line)

            # Reorder remaining waitlist
            self._reorder_waitlist()
            
            # Clear all related caches
            self._clear_event_cache()

            logger.info(
                f"Successfully processed cancellation for registration {cancelled_registration.id}"
            )

            return {
                'success': True,
                'message': 'Registration cancelled successfully'
            }

        except Exception as e:
            logger.error(f"Cancellation processing failed: {str(e)}")
            raise

    def _promote_registration(self, registration):
        """Promote a registration from waitlist to registered"""
        try:
            registration.status = 'registered'
            registration.waitlist_position = None
            registration.save()
            
            # Send promotion email
            try:
                send_promotion_email(registration)
            except Exception as e:
                logger.error(f"Failed to send promotion email: {str(e)}")
                # Don't fail the promotion if email fails

        except Exception as e:
            logger.error(f"Failed to promote registration {registration.id}: {str(e)}")
            raise

    def _reorder_waitlist(self):
        """Reorder waitlist positions after changes"""
        try:
            waitlist_registrations = EventRegistration.objects.filter(
                event=self.event,
                status='waitlist'
            ).order_by('registered_at')

            for index, registration in enumerate(waitlist_registrations):
                registration.waitlist_position = index + 1
                registration.save()

        except Exception as e:
            logger.error(f"Failed to reorder waitlist: {str(e)}")
            raise

    def _clear_event_cache(self):
        """Clear all related cache keys"""
        # Get all registrations for this event to clear their cache
        registrations = EventRegistration.objects.filter(event=self.event)
        cache_keys = [f'event_status_{self.event.id}', f'event_stats_{self.event.id}']
        
        # Add registration-specific cache keys
        for reg in registrations:
            cache_keys.append(
                f'registration_status_{self.event.id}_{reg.participant.id}'
            )
        
        cache.delete_many(cache_keys)


# Add this if you need rate limiting functionality
class RegistrationRateLimiter:
    def __init__(self, user_id, event_id):
        self.cache_key = f'registration_attempt_{user_id}_{event_id}'
        self.timeout = getattr(settings, 'REGISTRATION_RATE_LIMIT_SECONDS', 60)

    def check_rate_limit(self):
        """Return True if rate limit allows registration, False otherwise"""
        if cache.get(self.cache_key):
            return False
        cache.set(self.cache_key, True, self.timeout)
        return True