from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from profiles.models import Profile  # Use the Profile model from profiles app
from django.utils.translation import gettext_lazy as _
from django.db.models import Max, Q
from rest_framework import serializers
from django.db import transaction
import logging
from django.core.cache import cache



# Set up logging
logger = logging.getLogger(__name__)


class EventCategory(models.Model):
    name = models.CharField(max_length=100, help_text="Enter the event category name.")
    description = models.TextField(blank=True, help_text="Brief description of the category.")

    class Meta:
        verbose_name_plural = "Event Categories"

    def __str__(self):
        return self.name

class EventManager(models.Manager):
    def with_status(self):
        now = timezone.now()
        return self.annotate(
            status=models.Case(
                models.When(start_date__gt=now, then=models.Value('upcoming')),
                models.When(start_date__lte=now, end_date__gte=now, then=models.Value('ongoing')),
                models.When(end_date__lt=now, then=models.Value('completed')),
                default=models.Value('cancelled'),
                output_field=models.CharField(),
            )
        )

    def clean(self):
        if self.start_date >= self.end_date:
            raise ValidationError('Start date must be before end date.')




class Event(models.Model):
    EVENT_TYPE_CHOICES = [
        ('physical', 'Physical Event'),
        ('text', 'Text-Based Event'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('canceled', 'Canceled')
    ]
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='published'
    )
    allow_cancellation = models.BooleanField(
        default=True, 
        help_text="Allow participants to cancel their registration"
    )
    
    cancellation_deadline = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Deadline for registration cancellation"
    )
    title = models.CharField(max_length=200, help_text="Enter the event title.")
    description = models.TextField(help_text="Event description")
    event_type = models.CharField(max_length=10, choices=EVENT_TYPE_CHOICES, default='physical')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    location = models.CharField(max_length=200, help_text="Event location (optional for text-based events).", blank=True, null=True)
    max_participants = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum number of participants.")
    is_public = models.BooleanField(default=True)
    is_waitlist_open = models.BooleanField(default=True)
    category = models.ForeignKey(EventCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    image = models.ImageField(upload_to='event_images/', null=True, blank=True)
    campus = models.ForeignKey(Profile, on_delete=models.SET_NULL, null=True, related_name='campus_events')
    organizer = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='organized_events')
   
     
     
    # For text-based events
    content = models.TextField(blank=True, null=True, help_text="Content for text-based events")
    attachments = models.FileField(upload_to='event_attachments/', null=True, blank=True)
    
    objects = EventManager()

    def save(self, *args, **kwargs):
        if not self.campus and self.organizer:
            self.campus = self.organizer
        super().save(*args, **kwargs)
    
    def determine_registration_status(self):
        """
        Centralized method to determine registration status.
        
        Returns:
        - 'registered' if spots are available
        - 'waitlist' if event is full
        """
        if not self.max_participants:
            return 'registered'
        
        registered_count = self.registrations.filter(status='registered').count()
        return 'registered' if registered_count < self.max_participants else 'waitlist'
        
    def calculate_next_waitlist_position(self):
        """
        Calculate the next waitlist position, reordering if needed.
        
        Returns:
        - Next available waitlist position
        """
        with transaction.atomic():
            waitlist_registrations = self.registrations.filter(
                status='waitlist'
            ).order_by('waitlist_position')
            
            # Reorder and reassign positions if there are gaps
            for index, registration in enumerate(waitlist_registrations, 1):
                registration.waitlist_position = index
                registration.save()
            
            return waitlist_registrations.count() + 1
    
    @property
    def is_full(self):
        """Check if event has reached maximum participants."""
        return (
            self.max_participants is not None and 
            self.registrations.filter(status='registered').count() >= self.max_participants
        )
    
    
    def is_registration_open(self):
        """
        Check if registration is currently open
        """
        now = timezone.now()
        return (
            self.start_date <= now and 
            (not self.end_date or now <= self.end_date)
        )
    def is_cancellation_allowed(self):
        """
        Comprehensive cancellation eligibility check with detailed status
        """
        current_time = timezone.now()

        # Check if cancellation is globally disabled
        if not self.allow_cancellation:
            return False, "Cancellations are not allowed for this event"
        
        # Check if event has already started
        if self.start_date and current_time > self.start_date:
            return False, "Cannot cancel after event has started"
        
        # Check specific cancellation deadline
        if self.cancellation_deadline and current_time > self.cancellation_deadline:
            return False, "Cancellation deadline has passed"
        
        # Optional: 24-hour before event cancellation rule
        if self.start_date:
            cancellation_cutoff = self.start_date - timezone.timedelta(days=1)
            if current_time > cancellation_cutoff:
                return False, "Cancellations are only allowed up to 24 hours before the event"
        
        return True, "Cancellation allowed"
    @property
    def spots_left(self):
        # Adjust logic if needed
        registered_count = self.registrations.filter(status='registered').count()
        return max(0, self.max_participants - registered_count)

    @transaction.atomic
    def register_participant(self, user_profile, registration_data):
        # Count current registrations
        registered_count = self.registrations.filter(status='registered').count()
        
        # Determine registration status
        if self.max_participants is None:
            status = 'registered'
        elif registered_count < self.max_participants:
            status = 'registered'
        else:
            status = 'waitlist'
        
        # Create registration
        registration = EventRegistration.objects.create(
            event=self,
            participant=user_profile,
            status=status,
            **registration_data
        )
        
        # If waitlisted, set waitlist position
        if status == 'waitlist':
            registration.waitlist_position = (
                self.registrations.filter(status='waitlist')
                .aggregate(Max('waitlist_position'))['waitlist_position__max'] or 0
            ) + 1
            registration.save()
        
        return registration, status
    def can_register(self, user_profile):
        """
        Check if a user can register for this event.
        
        Args:
            user_profile: User's profile
        
        Returns:
            Tuple (can_register, status_message)
        """
        # Check for existing registration
        existing_registration = self.registrations.filter(
            participant=user_profile,
            status__in=['registered', 'waitlist']
        ).first()
        
        if existing_registration:
            return False, f"Already {existing_registration.get_status_display().lower()} for this event"
        
        # Check event availability
        if self.is_full:
            return self.is_waitlist_open, 'Event is full' if not self.is_waitlist_open else 'Added to waitlist'
        
        return True, 'Registration available'


class EventRegistration(models.Model):
    REGISTRATION_STATUS = (
        ('registered', 'Registered'),
        ('waitlist', 'Waitlisted'),
        ('cancelled', 'Cancelled')
    )
    
    event = models.ForeignKey(
        'Event', 
        on_delete=models.CASCADE, 
        related_name='registrations'
    )
    participant = models.ForeignKey(
        'profiles.Profile', 
        on_delete=models.CASCADE
    )
    registration_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, 
        choices=REGISTRATION_STATUS, 
        default='registered'
    )
    email = models.EmailField(null=True, blank=True)
    name = models.CharField(max_length=255)
    waitlist_position = models.PositiveIntegerField(null=True, blank=True)
    attended = models.BooleanField(default=False)

    class Meta:
        unique_together = [['event', 'participant']]
        ordering = ['registration_date']
        indexes = [
            models.Index(fields=['status', 'event']),
            models.Index(fields=['registration_date']),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Prevent duplicate registrations
            existing = EventRegistration.objects.filter(
                event=self.event,
                participant=self.participant
            ).exclude(pk=self.pk).first()

            if existing:
                raise ValidationError("Registration already exists for this event.")

            # Existing logic for status and waitlist
            if not self.pk:  
                self.status = self.event.determine_registration_status()
                if self.status == 'waitlist':
                    self.waitlist_position = self.event.calculate_next_waitlist_position()
            
            super().save(*args, **kwargs)
    def cancel_registration(self):
        """
        Advanced cancellation logic with comprehensive checks
        """
        if self.status == 'cancelled':
            raise ValidationError("Registration is already cancelled")
        
        with transaction.atomic():
            was_registered = self.status == 'registered'
            self.status = 'cancelled'
            self.waitlist_position = None
            self.save()
            
            # Logging cancellation
            RegistrationCancellationLog.objects.create(
                event=self.event,
                user=self.participant.user,  # Assuming Profile has a user relationship
                original_status=self.status
            )
            
            # Promote from waitlist if a registered spot was freed
            if was_registered:
                self._promote_from_waitlist()
    
    def _promote_from_waitlist(self):
        """
        Promote next waitlisted participant to registered status.
        """
        waitlist_registrations = self.event.registrations.filter(
            status='waitlist'
        ).order_by('waitlist_position')
        
        for registration in waitlist_registrations:
            if self.event.spots_left > 0:
                registration.status = 'registered'
                registration.waitlist_position = None
                registration.save()
                
                # Trigger notification for promoted registration
                self._send_promotion_notification(registration)
            else:
                break
    
    def _send_promotion_notification(self, registration):
        """
        Send email notification for waitlist promotion.
        """
        from .utils import send_promotion_email  # Avoid circular import
        try:
            send_promotion_email(registration)
        except Exception as e:
            # Log error without stopping the process
            logger.error(f"Failed to send promotion email: {e}")

    def __str__(self):
        return f"{self.name} - {self.event} ({self.get_status_display()})"
    
# Recommended additional model for logging
class RegistrationCancellationLog(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    original_status = models.CharField(max_length=20)
    cancelled_at = models.DateTimeField(auto_now_add=True)
    
class Comment(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='user_comments')  # Profile is used here
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    likes = models.ManyToManyField(Profile, through='CommentLike', related_name='liked_comments')  # Profile is used here
    is_edited = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']  # Order comments by creation time

    def save(self, *args, **kwargs):
        if self.pk:  # Mark as edited if it's an update
            self.is_edited = True
        super().save(*args, **kwargs)


class CommentLike(models.Model):
    user = models.ForeignKey(Profile, on_delete=models.CASCADE)  # Profile is used here
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'comment']  # Ensures one like per user-comment pair

    def __str__(self):
        return f"{self.user} likes {self.comment}"



