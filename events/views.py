import json
import logging
from time import sleep
# views.py
from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db import DatabaseError, transaction
from django.db.models import Count, F, Max, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.html import strip_tags
from django.views import View
from django.views.decorators.http import require_POST, require_http_methods
from django.views.generic import CreateView, DeleteView, DetailView, ListView
from django.views.generic.edit import FormMixin
from .managers import *
from notifications.bulk import notify_all_users
from profiles.models import Profile
from .forms import CommentForm, EventForm, EventRegistrationForm
from .models import Comment, Event, EventRegistration
from .serializers import CommentSerializer
from django.urls import reverse
# views.py
from django.views.generic import DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils.log import log_response



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

class EventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    form_class = EventForm
    template_name = 'events/create_event.html'
    success_url = reverse_lazy('events:event_list')

    @transaction.atomic
    def form_valid(self, form):
        form.instance.organizer = self.request.user.profile
        form.instance.campus = self.request.user.profile.campus
        response = super().form_valid(form)
        
        if form.cleaned_data.get('is_public'):
            notify_all_users("New Event")
        
        messages.success(self.request, "Event created successfully!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Invalid form submission.")
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
# Update the registration view to handle name validation properly
#views.py
class EventRegistrationView(View):
    @method_decorator(login_required)
    def post(self, request, event_id):
        try:
            event = get_object_or_404(Event, id=event_id)
            manager = RegistrationManager(event, request.user)
            result = manager.register()
            
            return JsonResponse(result, 
                              status=200 if result['success'] else 400)
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=500)

class EventCancellationView(View):
    @method_decorator(login_required)
    def post(self, request, event_id):
        try:
            event = get_object_or_404(Event, id=event_id)
            registration = get_object_or_404(
                EventRegistration,
                event=event,
                participant=request.user.profile,
                status__in=['registered', 'waitlist']
            )
            
            manager = WaitlistManager(event)
            result = manager.process_cancellation(registration)
            
            return JsonResponse(result, status=200)
        except Exception as e:
            logger.error(f"Cancellation error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred'
            }, status=500)

class EventStatusView(View):
    @method_decorator(login_required)
    def get(self, request, event_id):
        try:
            event = get_object_or_404(Event, id=event_id)
            
            # Try to get cached status first
            cache_key = f'event_status_{event_id}'
            status_data = cache.get(cache_key)
            
            if not status_data:
                registration = EventRegistration.objects.filter(
                    event=event,
                    participant=request.user.profile
                ).first()
                
                registered_count = EventRegistration.objects.filter(
                    event=event,
                    status='registered'
                ).count()
                
                waitlist_count = EventRegistration.objects.filter(
                    event=event,
                    status='waitlist'
                ).count()
                
                status_data = {
                    'success': True,
                    'total_spots': event.max_participants,
                    'spots_left': (event.max_participants - registered_count 
                                 if event.max_participants else None),
                    'registered_count': registered_count,
                    'waitlist_count': waitlist_count,
                    'is_full': (event.max_participants and 
                               registered_count >= event.max_participants),
                    'user_status': {
                        'is_registered': False,
                        'status': None,
                        'waitlist_position': None
                    }
                }
                
                if registration:
                    status_data['user_status'] = {
                        'is_registered': True,
                        'status': registration.status,
                        'waitlist_position': (registration.waitlist_position 
                                           if registration.status == 'waitlist' 
                                           else None)
                    }
                
                # Cache for 1 minute
                cache.set(cache_key, status_data, 60)
            
            return JsonResponse(status_data)
            
        except Exception as e:
            logger.error(f"Error getting event status: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Unable to get event status'
            }, status=500)

class WaitlistPositionView(View):
    @method_decorator(login_required)
    def get(self, request, event_id):
        try:
            event = get_object_or_404(Event, id=event_id)
            registration = get_object_or_404(
                EventRegistration,
                event=event,
                participant=request.user.profile,
                status='waitlist'
            )
            
            return JsonResponse({
                'success': True,
                'position': registration.waitlist_position,
                'total_waitlist': EventRegistration.objects.filter(
                    event=event,
                    status='waitlist'
                ).count()
            })
            
        except EventRegistration.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Not on waitlist'
            }, status=404)
        except Exception as e:
            logger.error(f"Error checking waitlist position: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Unable to check waitlist position'
            }, status=500)
            
            
# views.py
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
import json

from .managers import RegistrationManager, WaitlistManager
from .models import Event, EventRegistration

@login_required
@require_POST
@csrf_protect
def register_event(request):
    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')
        name = data.get('name')
        email = data.get('email')

        # Fetch the event
        event = Event.objects.get(id=event_id)

        # Use the RegistrationManager to handle registration
        registration_manager = RegistrationManager(event, request.user)
        result = registration_manager.register()

        # Prepare the response data
        response_data = {
            'success': result['success'],
            'status': result.get('status'),
            'waitlist_position': result.get('waitlist_position'),
            'spots_left': event.spots_left,
            'waitlist_count': event.waitlist_count,
            'error': result.get('error', '')
        }

        return JsonResponse(response_data)

    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Event not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@login_required
@require_POST
@csrf_protect
def cancel_registration(request):
    try:
        data = json.loads(request.body)
        event_id = data.get('event_id')

        # Fetch the event and existing registration
        event = Event.objects.get(id=event_id)
        registration = EventRegistration.objects.get(
            event=event, 
            participant=request.user.profile
        )

        # Use the WaitlistManager to process cancellation
        waitlist_manager = WaitlistManager(event)
        result = waitlist_manager.process_cancellation(registration)

        # Prepare the response data
        response_data = {
            'success': result['success'],
            'message': result.get('message', 'Registration cancelled'),
            'spots_left': event.spots_left,
            'waitlist_count': event.waitlist_count
        }

        return JsonResponse(response_data)

    except Event.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Event not found'}, status=404)
    except EventRegistration.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Registration not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)