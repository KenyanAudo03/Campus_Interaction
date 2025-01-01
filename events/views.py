import logging
import time
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView
from django.views.generic.edit import FormMixin
from .forms import CommentForm, EventForm, EventRegistrationForm
from .models import Comment, Event, EventRegistration, RegistrationCancellationLog
from notifications.bulk import notify_all_users
from profiles.models import Profile
from django.core.mail import send_mail
from .managers import *
from .utils import send_cancellation_confirmation_email, generate_google_calendar_url
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import EventUpdateSerializer


logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 60
EVENT_STATS_CACHE_KEY = 'event_stats_{event_id}'
REGISTRATION_STATUS_CACHE_KEY = 'registration_status_{event_id}_{profile_id}'


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
        if queryset is None:
            queryset = self.get_queryset()
        queryset = queryset.prefetch_related('registrations')
        return get_object_or_404(queryset, id=self.kwargs.get('event_id'))

    def get_registration_status(self, event, user_profile):
        cache_key = REGISTRATION_STATUS_CACHE_KEY.format(event_id=event.id, profile_id=user_profile.id)
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
            cache.set(cache_key, status, CACHE_TIMEOUT)
        return status

    def get_event_stats(self, event):
        cache_key = EVENT_STATS_CACHE_KEY.format(event_id=event.id)
        stats = cache.get(cache_key)
        if not stats:
            registered_count = event.registrations.filter(status='registered').count()
            waitlist_count = event.registrations.filter(status='waitlist').count()
            spots_left = (event.max_participants - registered_count if event.max_participants else None)
            stats = {
                'registered_count': registered_count,
                'waitlist_count': waitlist_count,
                'spots_left': spots_left,
                'is_full': (event.max_participants and registered_count >= event.max_participants),
                'has_waitlist': waitlist_count > 0,
                'total_participants': registered_count + waitlist_count
            }
            cache.set(cache_key, stats, CACHE_TIMEOUT)
        return stats

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object
        user_profile = self.request.user.profile
        registration_status = self.get_registration_status(event, user_profile)
        event_stats = self.get_event_stats(event)
        initial_form_data = {
            'name': self.request.user.get_full_name() or self.request.user.username,
            'email': self.request.user.email
        }
        google_calendar_link = generate_google_calendar_url(event)
        context.update({
            'user_registered': registration_status['is_registered'],
            'registration': registration_status['registration'],
            'registration_status': registration_status['status'],
            'waitlist_position': registration_status['waitlist_position'],
            'registered_count': event_stats['registered_count'],
            'waitlist_count': event_stats['waitlist_count'],
            'spots_left': event_stats['spots_left'],
            'is_full': event_stats['is_full'],
            'has_waitlist': event_stats['has_waitlist'],
            'total_participants': event_stats['total_participants'],
            'registration_form': EventRegistrationForm(initial=initial_form_data),
            'comment_form': self.get_form(),
            'comments': self.object.comments.all(),
            'is_waitlist_open': getattr(event, 'is_waitlist_open', True),
            'can_register': not event_stats['is_full'] or event.is_waitlist_open,
            'google_calendar_link': google_calendar_link,
            'show_waitlist_button': (
                event_stats['is_full'] and event.is_waitlist_open and not registration_status['is_registered']
            ),
            'show_register_button': (
                not event_stats['is_full'] and not registration_status['is_registered']
            )
        })
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                manager = RegistrationManager(self.object, request.user)
                result = manager.register()
                self.clear_related_cache()
                return JsonResponse(result, status=200 if result['success'] else 400)
            except Exception as e:
                logger.error(f"Registration error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': 'An unexpected error occurred'
                }, status=500)
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        comment = form.save(commit=False)
        comment.event = self.object
        comment.author = self.request.user
        comment.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('event_detail', kwargs={'event_id': self.object.id})

    def clear_related_cache(self):
        cache.delete_many([
            REGISTRATION_STATUS_CACHE_KEY.format(event_id=self.object.id, profile_id=self.request.user.profile.id),
            EVENT_STATS_CACHE_KEY.format(event_id=self.object.id)
        ])


class MultiStepEventCreateView(LoginRequiredMixin, CreateView):
    model = Event
    template_name = 'events/create_event.html'
    form_class = EventForm
    success_url = reverse_lazy('events:event_list')

    @transaction.atomic
    def form_valid(self, form):
        form.instance.organizer = self.request.user.profile
        form.instance.campus = self.request.user.profile.campus
        response = super().form_valid(form)
        if form.cleaned_data.get('is_public'):
            notify_all_users("New Event Created")
        messages.success(self.request, "Event created successfully!")
        return response

    def form_invalid(self, form):
        messages.error(self.request, "Please check the form and try again.")
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
        comments = Comment.objects.filter(event=event).select_related(
            'user__user'
        ).prefetch_related('replies').order_by('-created_at')
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
    try:
        event = get_object_or_404(Event, id=event_id)
        user_status = {
            'is_registered': False,
            'status': None
        }
        status_data = {
            'success': True,
            'total_spots': event.max_participants,
            'spots_left': event.spots_left,
            'is_full': event.is_full,
            'is_waitlist_open': event.is_waitlist_open,
            'event_start_date': event.start_date.isoformat() if event.start_date else None,
            'registration_open': event.is_registration_open(),
            'registration_deadline': event.end_date.isoformat() if event.end_date else None,
            'user_status': user_status
        }
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
    logger.info(f"Cancellation attempt: User {request.user.id}, Event {event_id}")
    if request.method != 'POST':
        logger.warning(f"Invalid method for cancellation: {request.method}")
        return JsonResponse({
            'success': False,
            'error': 'Method not allowed. Use POST.',
            'status_code': 'METHOD_NOT_ALLOWED'
        }, status=405)

    try:
        event = get_object_or_404(Event, id=event_id)
        can_cancel, reason = event.is_cancellation_allowed()
        if not can_cancel:
            logger.info(f"Cancellation not allowed: {reason}")
            return JsonResponse({
                'success': False,
                'error': reason,
                'status_code': 'CANCELLATION_NOT_ALLOWED'
            }, status=400)

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

        logger.info(f"Cancellation details: Registration {registration.id}, Status {registration.status}")
        registration.cancel_registration()

        try:
            send_cancellation_confirmation_email(request.user.profile, event)
        except Exception as email_error:
            logger.error(f"Email sending failed during cancellation: {email_error}")

        response_data = {
            'success': True,
            'message': 'Registration cancelled successfully',
            'previous_status': registration.status,
            'spots_left': event.spots_left,
            'max_participants': event.max_participants,
            'waitlist_promoted': True
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



@login_required
def register_event(request, event_id):
    """
    Enhanced event registration with improved error handling and flexibility.
    """
    max_retries = 3
    backoff_time = 0.5  # Initial backoff time in seconds

    for attempt in range(max_retries):
        try:
            with transaction.atomic():
                try:
                    event = Event.objects.select_for_update(nowait=True).get(id=event_id)
                except DatabaseError:
                    if attempt < max_retries - 1:
                        time.sleep(backoff_time)  # Exponential backoff
                        backoff_time *= 2
                        continue
                    else:
                        return JsonResponse({
                            'success': False,
                            'error': 'Event is currently being processed. Please try again later.'
                        }, status=409)

                user_profile = request.user.profile

                # Remove any existing registrations to allow re-registration
                EventRegistration.objects.filter(event=event, participant=user_profile).delete()

                # Create and validate form
                form = EventRegistrationForm(request.POST, event=event, user=request.user)

                if not form.is_valid():
                    return JsonResponse({'success': False, 'errors': form.errors}, status=400)

                # Determine registration status
                registered_count = event.registrations.filter(status='registered').count()
                registration_status = 'registered' if event.max_participants is None or registered_count < event.max_participants else 'waitlist'

                # Create registration
                registration = form.save(commit=False)
                registration.event = event
                registration.participant = user_profile
                registration.status = registration_status
                registration.save()

                # Send registration email
                try:
                    send_registration_email(registration)
                except Exception as email_error:
                    logger.error(f"Failed to send registration email: {email_error}", exc_info=True)

                return JsonResponse({
                    'success': True,
                    'status': registration.status,
                    'message': 'Successfully registered' if registration.status == 'registered' else f'Added to waitlist (Position: {registration.waitlist_position})',
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
                return JsonResponse({'success': False, 'error': 'Registration failed. Please try again.'}, status=500)

    logger.error(f"Registration error: {outer_error}", exc_info=True)
    return JsonResponse({'success': False, 'error': 'Registration failed. Please try again.'}, status=500)


class EventUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, event_id, user):
        try:
            event = Event.objects.get(id=event_id)
            if event.organizer.user != user:
                return None
            return event
        except Event.DoesNotExist:
            return None

    def put(self, request, event_id, *args, **kwargs):
        event = self.get_object(event_id, request.user)
        if not event:
            return Response(
                {"error": "You do not have permission to edit this event or event does not exist."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = EventUpdateSerializer(event, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

