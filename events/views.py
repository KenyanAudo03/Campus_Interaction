from ast import parse
import logging
import time
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db import  DatabaseError, transaction
from django.db.models import  Max, Q, F
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
import pytz
from django.utils import timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo 
from django.views import View
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DeleteView, DetailView, ListView
from django.views.generic.edit import FormMixin
from .managers import *
from notifications.bulk import notify_all_users
from profiles.models import Profile
from .forms import CommentForm, EventForm, EventRegistrationForm
from .models import Comment, Event, EventRegistration,RegistrationCancellationLog
from django.urls import reverse
from django.core.mail import send_mail
from django.core.exceptions import ValidationError,ObjectDoesNotExist
import json



# Set up logging
logger = logging.getLogger(__name__)


class EventListView(LoginRequiredMixin, ListView):
    model = Event
    template_name = 'events/event_list.html'
    context_object_name = 'events'
    paginate_by = 12

    def get_queryset(self):
        queryset = Event.objects.all().order_by('-start_date').prefetch_related('comments')
        status_filter = self.request.GET.get('status')
        campus_filter = self.request.GET.get('campus')

        if status_filter:
            now = timezone.now()
            if status_filter == 'upcoming':
                queryset = queryset.filter(start_date__gte=now)
            elif status_filter == 'ongoing':
                queryset = queryset.filter(start_date__lte=now, end_date__gte=now)
            elif status_filter == 'completed':
                queryset = queryset.filter(end_date__lt=now)

        if campus_filter:
            queryset = queryset.filter(campus__campus=campus_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campuses'] = Profile.objects.values_list('campus', flat=True).distinct()
        for event in context['events']:
            event.comments_count = event.comments.count()
            
            if event.event_type == 'text':
                 event.display_location = 'Online/Text-Based Event'
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('HX-Request'):
            return render(self.request, 'events/partials/event_list_content.html', context)
        return super().render_to_response(context, **response_kwargs)

class EventDetailView(LoginRequiredMixin, FormMixin, DetailView):
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'
    pk_url_kwarg = 'event_id'
    form_class = CommentForm

    def get_object(self, queryset=None):
        """Get event with prefetched registrations for efficient counting"""
        if queryset is None:
            queryset = self.get_queryset()
            
        queryset = queryset.prefetch_related('registrations')
        return get_object_or_404(queryset, id=self.kwargs.get('event_id'))

    def get_registration_status(self, event, user_profile):
        """Get cached or fresh registration status"""
        cache_key = f'registration_status_{event.id}_{user_profile.id}'
        status = cache.get(cache_key)
        
        if not status:
            registration = EventRegistration.objects.filter(
                event=event,
                participant=user_profile,
                status__in=['registered', 'waitlist']
            ).first()

            status = {
                'is_registered': registration is not None,
                'registration': registration,
                'status': getattr(registration, 'status', None),
                'waitlist_position': getattr(registration, 'waitlist_position', None)
            }
            
            # Cache for 1 minute
            cache.set(cache_key, status, 60)
            
        return status

    def get_event_stats(self, event):
        """Get cached or fresh event statistics"""
        cache_key = f'event_stats_{event.id}'
        stats = cache.get(cache_key)
        
        if not stats:
            registered_count = event.registrations.filter(
                status='registered'
            ).count()
            
            waitlist_count = event.registrations.filter(
                status='waitlist'
            ).count()
            
            spots_left = (event.max_participants - registered_count 
                         if event.max_participants else None)
            
            stats = {
                'registered_count': registered_count,
                'waitlist_count': waitlist_count,
                'spots_left': spots_left,
                'is_full': (event.max_participants and 
                           registered_count >= event.max_participants),
                'has_waitlist': waitlist_count > 0,
                'total_participants': registered_count + waitlist_count
            }
            
            # Cache for 1 minute
            cache.set(cache_key, stats, 60)
            
        return stats

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        user_profile = self.request.user.profile
        
        # Get registration status and event stats
        registration_status = self.get_registration_status(event, user_profile)
        event_stats = self.get_event_stats(event)
        participant=user_profile,
        # Create initial form data
        initial_form_data = {
            'name': self.request.user.get_full_name() or self.request.user.username,
            'email': self.request.user.email
        }
        
        # Generate Google Calendar link
        google_calendar_link = generate_google_calendar_url(event)  # You'll need to import this function

        context.update({
            # Registration status
            'user_registered': registration_status['is_registered'],
            'registration': registration_status['registration'],
            'registration_status': registration_status['status'],
            'waitlist_position': registration_status['waitlist_position'],
            
            # Event statistics
            'registered_count': event_stats['registered_count'],
            'waitlist_count': event_stats['waitlist_count'],
            'spots_left': event_stats['spots_left'],
            'is_full': event_stats['is_full'],
            'has_waitlist': event_stats['has_waitlist'],
            'total_participants': event_stats['total_participants'],
            
            # Forms and additional data
            'registration_form': EventRegistrationForm(initial=initial_form_data),
            'comment_form': self.get_form(),
            
            'comments': self.object.comments.all(),
            # Waitlist settings
            'is_waitlist_open': getattr(event, 'is_waitlist_open', True),
            'can_register': not event_stats['is_full'] or event.is_waitlist_open,
            
            'google_calendar_link': google_calendar_link,
            # Additional context for template
            'show_waitlist_button': (
                event_stats['is_full'] and 
                event.is_waitlist_open and 
                not registration_status['is_registered']
            ),
            'show_register_button': (
                not event_stats['is_full'] and 
                not registration_status['is_registered']
            )
        })
        
        return context

    def post(self, request, *args, **kwargs):
        """Handle both AJAX registration requests and comment submissions"""
        self.object = self.get_object()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                # Handle registration through RegistrationManager
                manager = RegistrationManager(self.object, request.user)
                result = manager.register()
                
                # Clear relevant caches
                cache.delete(f'registration_status_{self.object.id}_{request.user.profile.id}')
                cache.delete(f'event_stats_{self.object.id}')
                
                return JsonResponse(result, 
                                  status=200 if result['success'] else 400)
            except Exception as e:
                logger.error(f"Registration error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'An unexpected error occurred'
                }, status=500)
        
        # Handle comment form submission
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        """Handle valid comment form submission"""
        comment = form.save(commit=False)
        comment.event = self.object
        comment.author = self.request.user
        comment.save()
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect URL after successful comment submission"""
        return reverse('event_detail', kwargs={'event_id': self.object.id})

class MultiStepEventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    template_name = 'events/create_event.html'
    form_class = EventForm
    success_url = reverse_lazy('events:event_list')

    @transaction.atomic
    def form_valid(self, form):
        # Additional processing for multi-step form submission
        form.instance.organizer = self.request.user.profile
        form.instance.campus = self.request.user.profile.campus
        
        response = super().form_valid(form)
        
        # Optionally send notifications
        if form.cleaned_data.get('is_public'):
            notify_all_users("New Event Created")
        
        messages.success(self.request, "Event created successfully!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please check the form and try again.")
        print(form.errors)
        return super().form_invalid(form)

class CommentCreateView(LoginRequiredMixin, View):
    @transaction.atomic
    def post(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        form = CommentForm(request.POST)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if form.is_valid():
            comment = form.save(commit=False)
            comment.event = event
            comment.user = request.user.profile
            comment.save()

            if is_ajax:
                comment_html = render_to_string('events/partials/comment.html', {
                    'comment': comment,
                    'event': event
                }, request=request)
                return JsonResponse({
                    'status': 'success',
                    'comment_html': comment_html,
                    'comment_id': comment.id
                })
            
            messages.success(request, 'Comment added successfully!')
            return redirect('events:event_detail', event_id=event_id)
        
        if is_ajax:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid form data',
                'errors': form.errors
            }, status=400)
        
        messages.error(request, 'Please correct the errors below.')
        return redirect('events:event_detail', event_id=event_id)

        

class LoadMoreCommentsView(LoginRequiredMixin, View):
    def get(self, request, event_id):
        event = get_object_or_404(Event, id=event_id)
        page = int(request.GET.get('page', 1))
        comments_per_page = 5

        comments = Comment.objects.filter(
            event=event
        ).select_related(
            'user__user'
        ).prefetch_related(
            'replies'
        ).order_by('-created_at')

        paginator = Paginator(comments, comments_per_page)

        try:
            comments_page = paginator.page(page)
        except (EmptyPage, InvalidPage):
            return JsonResponse({'comments_html': '', 'has_next': False})

        comments_html = render_to_string(
            'events/partials/comments_pagination.html',
            {'comments': comments_page, 'event': event},
            request=request
        )

        return JsonResponse({
            'comments_html': comments_html,
            'has_next': comments_page.has_next()
        })

class CommentLikeToggleView(LoginRequiredMixin, View):
    def post(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)
        if request.user.profile in comment.likes.all():
            comment.likes.remove(request.user.profile)
            is_liked = False
        else:
            comment.likes.add(request.user.profile)
            is_liked = True

        return JsonResponse({
            'status': 'success',
            'likes_count': comment.likes.count(),
            'is_liked': is_liked
        })

class EventDeleteView(LoginRequiredMixin, DeleteView):
    model = Event
    pk_url_kwarg = 'event_id'
    success_url = reverse_lazy('events:event_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.organizer.user != request.user and not request.user.is_staff:
            return JsonResponse({"status": "error", "message": "Permission denied"}, status=403)

        image_path = self.object.image.path if self.object.image else None
        self.object.delete()

        if image_path:
            try:
                default_storage.delete(image_path)
            except Exception as e:
                logger.error(f"Error deleting file {image_path}: {e}")
                return JsonResponse({
                    "status": "success",
                    "message": "Event deleted, but media file removal failed."
                }, status=500)

        messages.success(request, "Event deleted successfully.")
        return JsonResponse({"status": "success", "message": "Event deleted successfully."})

class CampusAutocompleteView(LoginRequiredMixin, View):
    def get(self, request):
        if 'term' in request.GET:
            query = request.GET.get('term')
            campuses = Profile.objects.filter(
                Q(campus__icontains=query)
            ).values('id', 'campus').distinct()[:10]

            results = [{
                'id': profile['id'],
                'label': profile['campus'],
                'value': profile['campus']
            } for profile in campuses]
            return JsonResponse(results, safe=False)

        return JsonResponse([], safe=False)



@login_required
def event_status_view(request, event_id):
    """
    API endpoint to get detailed event registration status, including user-specific details.
    """
    try:
        event = get_object_or_404(Event, id=event_id)
        user_status = {
            'is_registered': False,
            'status': None
        }
        
        # Prepare base event status data
        status_data = {
            'success': True,
            'total_spots': event.max_participants,
            'spots_left': event.spots_left,
            'is_full': event.is_full,
            'is_waitlist_open': event.is_waitlist_open,
            'event_start_date': event.start_date.isoformat() if event.start_date else None,
            'registration_open': event.is_registration_open(),  # Assume this is a method in the Event model
            'registration_deadline': event.end_date.isoformat() if event.end_date else None,
            'user_status': user_status
        }

        # Check user's registration if logged in
        if request.user.is_authenticated:
            user_profile = request.user.profile
            registration = event.registrations.filter(
                Q(participant=user_profile) & 
                Q(status__in=['registered', 'waitlist'])
            ).first()
            
            if registration:
                user_status['is_registered'] = True
                user_status['status'] = registration.status
                if registration.status == 'waitlist':
                    user_status['waitlist_position'] = registration.waitlist_position
            
            status_data['user_status'] = user_status
        
        return JsonResponse(status_data)
    
    except Event.DoesNotExist:
        logger.error(f"Event with ID {event_id} not found.")
        return JsonResponse({
            'success': False,
            'error': 'Event not found'
        }, status=404)
    
    except Exception as e:
        logger.error(f"Error retrieving event status: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred'
        }, status=500)

@login_required
def cancel_registration(request, event_id):
    """
    Comprehensive event registration cancellation handler
    """
    # Logging for debugging
    logger.info(f"Cancellation attempt: User {request.user.id}, Event {event_id}")

    if request.method != 'POST':
        logger.warning(f"Invalid method for cancellation: {request.method}")
        return JsonResponse({
            'success': False, 
            'error': 'Method not allowed. Use POST.',
            'status_code': 'METHOD_NOT_ALLOWED'
        }, status=405)
    
    try:
        # Retrieve the event first to validate its existence
        event = get_object_or_404(Event, id=event_id)
        
        # Comprehensive cancellation eligibility check
        can_cancel, reason = event.is_cancellation_allowed()
        if not can_cancel:
            logger.info(f"Cancellation not allowed: {reason}")
            return JsonResponse({
                'success': False,
                'error': reason,
                'status_code': 'CANCELLATION_NOT_ALLOWED'
            }, status=400)
        
        # Find the user's registration
        try:
            registration = EventRegistration.objects.get(
                event=event, 
                participant=request.user.profile,
                status__in=['registered', 'waitlist']
            )
        except EventRegistration.DoesNotExist:
            logger.warning(f"No active registration found for user {request.user.id}, event {event_id}")
            return JsonResponse({
                'success': False,
                'error': 'No active registration found',
                'status_code': 'NO_REGISTRATION'
            }, status=404)
        
        # Detailed logging
        logger.info(f"Cancellation details: Registration {registration.id}, Status {registration.status}")
        
        # Log cancellation event
        RegistrationCancellationLog.objects.create(
            event=event,
            user=request.user,
            original_status=registration.status,
            cancelled_at=timezone.now()
        )
        
        # Cancel the registration
        registration.cancel_registration()
        
        # Send cancellation confirmation email
        try:
            send_cancellation_confirmation_email(request.user.profile, event)
        except Exception as email_error:
            logger.error(f"Email sending failed during cancellation: {email_error}")
            # Note: We don't return an error here, as the cancellation itself was successful
        
        # Prepare comprehensive response
        response_data = {
            'success': True,
            'message': 'Registration cancelled successfully',
            'previous_status': registration.status,
            'spots_left': event.spots_left,
            'max_participants': event.max_participants,
            'waitlist_promoted': True  # Assuming promotion might have occurred
        }
        
        return JsonResponse(response_data)
    
    except Exception as unexpected_error:
        logger.error(f"Unexpected cancellation error: {unexpected_error}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected system error occurred',
            'status_code': 'SYSTEM_ERROR',
            'details': str(unexpected_error)
        }, status=500)

def send_cancellation_confirmation_email(user, event):
    """
    Comprehensive cancellation email
    """
    try:
        email_context = {
            'event_title': event.title,
            'event_date': event.start_date,
            'cancellation_time': timezone.now(),
            'spots_left_before': event.spots_left
        }
        
        # Use a template-based email for richer content
        send_mail(
            subject=f'Event Registration Cancelled: {event.title}',
            message=render_to_string('emails/cancellation_confirmation.html', email_context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=render_to_string('events/emails/cancellation_confirmation_html.html', email_context)
        )
    except Exception as e:
        logger.error(f"Cancellation email failed: {e}")
    
def _promote_from_waitlist(event):
    """
    Promote participants from waitlist to registered status
    """
    # Get waitlisted registrations ordered by waitlist position
    waitlist_registrations = EventRegistration.objects.filter(
        event=event, 
        status='waitlist'
    ).order_by('waitlist_position')
    
    # Iterate through waitlist and promote if spots are available
    for registration in waitlist_registrations:
        # Check if there are spots left
        if event.spots_left and event.spots_left > 0:
            # Change status to registered
            registration.status = 'registered'
            registration.waitlist_position = None
            registration.save()
            
            # Send promotion notification (optional)
            _send_waitlist_promotion_email(registration)
        else:
            # No more spots available, stop promoting
            break
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

@login_required
def register_event(request, event_id):
    """
    Enhanced event registration with improved error handling and flexibility
    """
    max_retries = 3
    backoff_time = 0.5  # Initial backoff time in seconds
    for attempt in range(max_retries):
        
        try:
            # Use select_for_update with nowait to prevent long-running locks
            with transaction.atomic():
                 # Example of handling potential locks
                try:
                    event = Event.objects.select_for_update(nowait=True).get(id=event_id)
                except DatabaseError:
                    if attempt < max_retries - 1:
                        time.sleep(backoff_time)  # Wait a bit before retrying
                        backoff_time *= 2  # Exponential backoff
                        continue
                    else:
                        return JsonResponse({
                            'success': False,
                            'error': 'Event is currently being processed. Please try again later.'
                        }, status=409)
                
                user_profile = request.user.profile
                
                # Explicit logging or check
                registered_count = event.registrations.filter(status='registered').count()
                logger.info(f"Registered count: {registered_count}")
                logger.info(f"Max participants: {event.max_participants}")
                
                # Remove any existing registrations to allow re-registration
                EventRegistration.objects.filter(
                    event=event, 
                    participant=user_profile
                ).delete()
                
                # Create and validate form
                form = EventRegistrationForm(
                    request.POST,
                    event=event,
                    user=request.user
                )
                
                if not form.is_valid():
                    return JsonResponse({
                        'success': False,
                        'errors': form.errors
                    }, status=400)
                
                # Determine registration status with atomic transaction
                try:
                    with transaction.atomic():
                        # Refresh the event to get the most current state
                        event.refresh_from_db()
                        
                        # Count registered participants
                        registered_count = event.registrations.filter(status='registered').count()
                        
                        # Prepare registration
                        registration = form.save(commit=False)
                        registration.event = event
                        registration.participant = user_profile
                        registration.name = form.cleaned_data['name']
                        registration.email = form.cleaned_data['email']
                        
                        # Determine registration status with more precise logic
                        if event.max_participants is None:
                            registration.status = 'registered'
                        elif registered_count < event.max_participants:
                            registration.status = 'registered'
                        else:
                            registration.status = 'waitlist'

                        # Save the registration
                        registration.save()

                    
                        # Send appropriate email using the utility functions
                        try:
                            registered_count = event.registrations.filter(status='registered').count()
                            if registered_count < event.max_participants:
                                # This means spots are available, so send regular registration email
                                send_registration_email(registration)
                            else:
                                # No spots left, send waitlist email
                                send_registration_email(registration)
                        except Exception as email_error:
                            logger.error(f"Failed to send registration email: {email_error}", exc_info=True)
                        # Return response
                        return JsonResponse({
                            'success': True,
                            'status': registration.status,
                            'message': ('Successfully registered' if registration.status == 'registered' 
                                        else f'Added to waitlist (Position: {registration.waitlist_position})'),
                            'waitlist_position': registration.waitlist_position if registration.status == 'waitlist' else None,
                            'spots_left': event.spots_left
                        })
                
                except Exception as outer_error:
                    if attempt < max_retries - 1:
                        time.sleep(backoff_time)
                        backoff_time *= 2  # Exponential backoff
                        continue
                    else:
                        logger.error(f"Registration error: {outer_error}", exc_info=True)
                        return JsonResponse({
                            'success': False,
                            'error': 'Registration failed. Please try again.'
                        }, status=500)
        except Exception as outer_error:
            logger.error(f"Registration error: {outer_error}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Registration failed. Please try again.'
            }, status=500)




def generate_google_calendar_url(event):
    """
    Generate a Google Calendar URL with timezone-aware handling
    """
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
    
    google_calendar_link = f"{base_url}?{urlencode(params)}"
    
    return google_calendar_link







def update_event(request, event_id):
    try:
        logger.info(f"Received update request for event {event_id}")
        logger.info(f"Content Type: {request.content_type}")

        # Extract payload
        if request.content_type.startswith('multipart/form-data'):
            payload_str = request.POST.get('payload', '{}')
        else:
            payload_str = request.body.decode('utf-8')
        logger.info(f"Raw Payload String: {payload_str}")
        
        try:
            body = json.loads(payload_str)
            logger.info(f"Parsed Payload: {body}")
        except json.JSONDecodeError as e:
            logger.error(f"Payload parsing error: {e}")
            return JsonResponse({'error': 'Invalid payload', 'details': str(e)}, status=400)

        if not body or (isinstance(body, dict) and len(body) == 0):
            logger.warning("No update data provided")
            return JsonResponse({'error': 'No update data provided', 'details': 'The payload is empty or invalid'}, status=400)

        event = get_object_or_404(Event, id=event_id)

        if not event.can_edit(request.user):
            return JsonResponse({'error': 'You do not have permission to edit this event', 'details': f'User {request.user.id} cannot edit event {event_id}'}, status=403)

        allowed_fields = [
            'title', 'description', 'start_date', 'end_date', 
            'location', 'max_participants', 'is_public', 
            'event_type', 'content', 'status', 
            'is_waitlist_open'
        ]

        update_count = 0
        for field, value in body.items():
            if field in allowed_fields:
                try:
                    if isinstance(value, str):
                        value = value.lower() in ['true', '1', 'yes']
                    if field in ['start_date', 'end_date']:
                        value = parse(value) if value else None
                    
                    setattr(event, field, value)
                    update_count += 1
                    logger.info(f"Updated field {field} to {value}")
                except Exception as e:
                    logger.warning(f"Error setting field {field}: {e}")

        if request.FILES:
            for file_key in ['image', 'attachments']:
                if file_key in request.FILES:
                    setattr(event, file_key, request.FILES[file_key])
                    logger.info(f"Uploaded {file_key}")

        event.save()

        return JsonResponse({
            'success': True, 
            'message': 'Event updated successfully',
            'updated_fields': list(body.keys()),
            'event': {
                'id': event.id,
                'title': event.title,
                'location': event.location,
                'start_date': event.start_date.isoformat() if event.start_date else None,
                'end_date': event.end_date.isoformat() if event.end_date else None,
            }
        })

    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)
    except Exception as e:
        logger.error(f"Unexpected error updating event: {str(e)}")
        return JsonResponse({'error': 'Update failed', 'details': str(e)}, status=400)