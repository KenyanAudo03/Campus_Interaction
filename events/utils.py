# utils.py
import time
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.core.cache import cache
import logging
import pytz
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def send_registration_email(registration):
    """Send registration confirmation or waitlist email to participant."""
    max_retries = 3
    backoff_time = 1  # Initial backoff time in seconds

    for attempt in range(max_retries):
        try:
            logger.info(f"Sending email for registration with status: {registration.status}")
            logger.info(f"Event max participants: {registration.event.max_participants}")
            logger.info(f"Current registered count: {registration.event.registrations.filter(status='registered').count()}")

            if not registration.name or not registration.email:
                raise ValueError("Registration must have both name and email")

            context = {
                'registration': registration,
                'event': registration.event,
                'name': registration.name,
                'status': registration.get_status_display(),
                'waitlist_position': registration.waitlist_position if registration.status == 'waitlist' else None
            }

            template = {
                'waitlist': 'events/emails/waitlist_confirmation.html',
                'registered': 'events/emails/registration_confirmation.html'
            }.get(registration.status, None)

            if not template:
                logger.warning(f"Unexpected registration status: {registration.status}")
                return

            subject = f"{registration.get_status_display()} - {registration.event.title}"
            html_message = render_to_string(template, context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[registration.email],
                html_message=html_message,
                fail_silently=False
            )

            logger.info(f"Registration email sent successfully to {registration.email} for event {registration.event.title}")
            break  # Break out of the loop if the email was sent successfully

        except Exception as e:
            logger.error(f"Error sending registration email to {registration.email} for event {registration.event.title}: {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff
            else:
                raise  # Re-raise the exception after the final attempt

def _send_waitlist_promotion_email(registration):
    """
    Send email to promote from waitlist to registered
    """
    try:
        send_mail(
            subject=f"Waitlist Promotion - {registration.event.title}",
            message=render_to_string('events/emails/waitlist_promotion.html', {
                'registration': registration,
                'event': registration.event,
                'name': registration.name,
            }),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[registration.email],
            html_message=render_to_string('events/emails/waitlist_promotion.html', {
                'registration': registration,
                'event': registration.event,
                'name': registration.name,
            }),
        )
    except Exception as email_error:
        logger.error(f"Failed to send waitlist promotion email: {email_error}", exc_info=True)
def send_promotion_email(registration):
    """Send email when participant is promoted from waitlist to registered."""
    max_retries = 3
    backoff_time = 1  # Initial backoff time in seconds

    for attempt in range(max_retries):
        try:
            subject = f"You're In! - {registration.event.title}"

            context = {
                'registration': registration,
                'event': registration.event,
                'name': registration.name
            }

            template = 'events/emails/promotion_notification.html'
            html_message = render_to_string(template, context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[registration.email],
                html_message=html_message,
                fail_silently=False
            )

            logger.info(f"Promotion email sent successfully to {registration.email} for event {registration.event.title}")
            break  # Break out of the loop if the email was sent successfully

        except Exception as e:
            logger.error(f"Error sending promotion email to {registration.email} for event {registration.event.title}: {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff_time)
                backoff_time *= 2  # Exponential backoff
            else:
                raise  # Re-raise the exception after the final attempt



def send_cancellation_confirmation_email(user_profile, event):
    """Send cancellation confirmation email to user."""
    try:
        email_context = {
            'event_title': event.title,
            'event_date': event.start_date,
            'cancellation_time': pytz.timezone.now(),
            'spots_left_before': event.spots_left
        }
        
        send_mail(
            subject=f'Event Registration Cancelled: {event.title}',
            message=render_to_string('emails/cancellation_confirmation.html', email_context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_profile.user.email],
            html_message=render_to_string('events/emails/cancellation_confirmation_html.html', email_context)
        )
    except Exception as e:
        logger.error(f"Cancellation email failed: {e}")

def generate_google_calendar_url(event):
    """Generate a Google Calendar URL with timezone-aware handling."""
    base_url = "https://www.google.com/calendar/render"
    
    # Convert to UTC using pytz
    utc = pytz.UTC
    start_date_utc = event.start_date.astimezone(utc)
    end_date_utc = event.end_date.astimezone(utc)
    
    params = {
        'action': 'TEMPLATE',
        'text': event.title,
        'dates': f"{start_date_utc.strftime('%Y%m%dT%H%M%SZ')}/{end_date_utc.strftime('%Y%m%dT%H%M%SZ')}",
        'details': event.description or '',
        'location': event.location or '',
        'crm': 'CONFIRMED'  # Optional: Sets event status
    }
    
    return f"{base_url}?{urlencode(params)}"

def clear_event_cache(event, profile_id=None):
    """Clear all related cache keys for an event."""
    cache_keys = [
        f'event_status_{event.id}',
        f'event_stats_{event.id}'
    ]
    
    if profile_id:
        cache_keys.append(f'registration_status_{event.id}_{profile_id}')
    
    cache.delete_many(cache_keys)