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
        # Debug logging
        logger.info(f"Sending email for registration with status: {registration.status}")
        logger.info(f"Event max participants: {registration.event.max_participants}")
        logger.info(f"Current registered count: {registration.event.registrations.filter(status='registered').count()}")

        if not registration.name or not registration.email:
            raise ValueError("Registration must have both name and email")

        subject = f"Registration Update - {registration.event.title}"
        
        context = {
            'registration': registration,
            'event': registration.event,
            'name': registration.name,
            'status': registration.get_status_display(),
            'waitlist_position': registration.waitlist_position if registration.status == 'waitlist' else None
        }

        # Determine template based on registration status
        if registration.status == 'waitlist':
            template = 'events/emails/waitlist_confirmation.html'
            subject = f"Waitlist Confirmation - {registration.event.title}"
        elif registration.status == 'registered':
            template = 'events/emails/registration_confirmation.html'
            subject = f"Registration Confirmed - {registration.event.title}"
        else:
            logger.warning(f"Unexpected registration status: {registration.status}")
            return

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

    except Exception as e:
        logger.error(f"Error sending registration email to {registration.email} for event {registration.event.title}: {e}")
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