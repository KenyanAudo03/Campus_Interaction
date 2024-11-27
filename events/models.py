from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from profiles.models import Profile  # Use the Profile model from profiles app
from django.utils.translation import gettext_lazy as _
from django.db.models import Max
from rest_framework import serializers
from django.db import transaction

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
        default='draft'
    )
    category = models.ForeignKey(EventCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    title = models.CharField(max_length=200, help_text="Enter the event title.")
    description = models.TextField(help_text="Event description")
    event_type = models.CharField(max_length=10, choices=EVENT_TYPE_CHOICES, default='physical')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    location = models.CharField(max_length=200, help_text="Event location (optional for text-based events).", blank=True, null=True)
    image = models.ImageField(upload_to='event_images/', null=True, blank=True)
    max_participants = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum number of participants.")
    is_public = models.BooleanField(default=True)
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
   

    @property
    def is_full(self):
        if self.max_participants is None:
            return False
        return self.registrations.filter(status='registered').count() >= self.max_participants

    @property
    def spots_left(self):
        if self.max_participants is None:
            return None
        registered_count = self.registrations.filter(status='registered').count()
        return max(0, self.max_participants - registered_count)




class EventRegistration(models.Model):
    REGISTRATION_STATUS = (
        ('registered', 'Registered'),
        ('waitlist', 'Waitlisted'),
        ('cancelled', 'Cancelled')
    )
    
    event = models.ForeignKey(
        'Event', 
        on_delete=models.CASCADE, 
        related_name='registrations',
        help_text=_("The event being registered for")
    )
    participant = models.ForeignKey(
        'profiles.Profile', 
        on_delete=models.CASCADE,
        help_text=_("The user registering for the event")
    )
    registration_date = models.DateTimeField(
    auto_now_add=True,
    help_text=_("When the registration was created"),
    
)
    attended = models.BooleanField(
        default=False,
        help_text=_("Whether the participant attended the event")
    )
    status = models.CharField(
        max_length=20, 
        choices=REGISTRATION_STATUS, 
        default='registered',
        help_text=_("Current status of the registration")
    )
    email = models.EmailField(
        null=True, 
        blank=True,
        help_text=_("Contact email for the registration")
    )
    name = models.CharField(
    max_length=255, 
    help_text=_("Full name of the participant"),
    null=False,  # Ensure this is set
    blank=False  # This prevents empty strings
)
    waitlist_position = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text=_("Position in the waitlist if applicable")
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['event', 'participant'], 
                name='unique_event_participant'
            )
        ]
        ordering = ['registration_date']
        indexes = [
            models.Index(fields=['status', 'event']),
            models.Index(fields=['registration_date']),
        ]

    def __str__(self):
        return f"{self.name} - {self.event} ({self.get_status_display()})"

    def clean(self):
        if self.status == 'waitlist' and self.waitlist_position is None:
            raise ValidationError({
                'waitlist_position': _('Waitlist position is required for waitlisted registrations.')
            })
        if self.status != 'waitlist' and self.waitlist_position is not None:
            raise ValidationError({
                'waitlist_position': _('Waitlist position should only be set for waitlisted registrations.')
            })
    def validate(self, data):
        if not data.get('name'):
            raise serializers.ValidationError({"name": "Name cannot be blank"})
        return data
    def save(self, *args, **kwargs):
        self.full_clean()
        
        if not self.pk:  # New registration
            current_registrations = EventRegistration.objects.filter(
                event=self.event, 
                status='registered'
            ).count()
            
            if self.event.max_participants and current_registrations >= self.event.max_participants:
                self.status = 'waitlist'
                last_position = EventRegistration.objects.filter(
                    event=self.event,
                    status='waitlist'
                ).aggregate(Max('waitlist_position'))['waitlist_position__max'] or 0
                self.waitlist_position = last_position + 1
        
        # Clear waitlist position if status is not waitlist
        if self.status != 'waitlist':
            self.waitlist_position = None
            
        super().save(*args, **kwargs)

    def cancel_registration(self):
        """
        Cancel this registration and move up waitlisted registrations if applicable.
        """
        with transaction.atomic():
            was_registered = self.status == 'registered'
            self.status = 'cancelled'
            self.waitlist_position = None
            self.save()
            
            if was_registered:
                # Try to move the first waitlisted person to registered
                next_waitlisted = EventRegistration.objects.filter(
                    event=self.event,
                    status='waitlist'
                ).order_by('waitlist_position').first()
                
                if next_waitlisted:
                    next_waitlisted.move_from_waitlist()
            
            return True

    def move_from_waitlist(self):
        """
        Attempt to move a waitlisted registration to registered status if space is available.
        """
        if self.status != 'waitlist':
            return False
            
        current_registrations = EventRegistration.objects.filter(
            event=self.event, 
            status='registered'
        ).count()
        
        # Use the new method name here as well
        spots_remaining = self.event.get_spots_remaining()
            
        if spots_remaining is None or spots_remaining > 0:
            self.status = 'registered'
            self.waitlist_position = None
            self.save()
            
            # Reorder remaining waitlist
            waitlist_registrations = EventRegistration.objects.filter(
                event=self.event,
                status='waitlist'
            ).order_by('waitlist_position')
            
            for i, registration in enumerate(waitlist_registrations, 1):
                registration.waitlist_position = i
                registration.save()
                
            return True
        return False
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


