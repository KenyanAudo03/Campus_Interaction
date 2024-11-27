# utils.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)
def send_registration_email(registration):
    """Send registration confirmation or waitlist email to participant."""
    try:
        subject = f"Registration Update - {registration.event.title}"
        
        context = {
            'registration': registration,
            'event': registration.event,
            'name': registration.name,
            'status': registration.get_status_display(),
            'waitlist_position': registration.waitlist_position
        }

        template = ('events/emails/registration_confirmation.html' 
                   if registration.status == 'registered' 
                   else 'events/emails/waitlist_confirmation.html')
        
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

    except Exception as e:
        logger.error(f"Error sending registration email: {str(e)}")
        raise

def send_promotion_email(registration):
    """Send email when participant is promoted from waitlist to registered."""
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

    except Exception as e:
        logger.error(f"Error sending promotion email: {str(e)}")
        raise