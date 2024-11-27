# events/api_views.py
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from .models import Event, EventRegistration, Comment
from .serializers import (
    EventSerializer, EventRegistrationSerializer,
    CommentSerializer
)
from .filters import EventFilter
# events/api_views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Event
from .serializers import EventUpdateSerializer



class IsOrganizerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.organizer.user == request.user or request.user.is_staff


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsOrganizerOrReadOnly]
    filterset_class = EventFilter  # Use the custom EventFilter class
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering_fields = ['start_date', 'created_at']

    def get_queryset(self):
        # Optimize queryset with related fields
        return Event.objects.all().select_related(
            'category', 'university', 'organizer'
        ).prefetch_related('comments', 'reactions')

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user.profile)

    @action(detail=True, methods=['post'])
    def register(self, request, pk=None):
        event = self.get_object()
        serializer = EventRegistrationSerializer(
            data={'event': event.id},
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save(participant=request.user.profile)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Comment.objects.filter(
            event_id=self.kwargs['event_pk']
        ).select_related('user').prefetch_related('likes', 'replies')

    def perform_create(self, serializer):
        event = Event.objects.get(pk=self.kwargs['event_pk'])
        serializer.save(event=event, user=self.request.user.profile)

    @action(detail=True, methods=['post'])
    def like(self, request, event_pk=None, pk=None):
        comment = self.get_object()
        user_profile = request.user.profile
        
        if user_profile in comment.likes.all():
            comment.likes.remove(user_profile)
            liked = False
        else:
            comment.likes.add(user_profile)
            liked = True
        
        return Response({
            'liked': liked,
            'likes_count': comment.likes.count()
        })
        
        
class EventUpdatePermission(permissions.BasePermission):
    """
    Custom permission to only allow event organizers or staff to update event
    """
    def has_object_permission(self, request, view, obj):
        # Allow staff or event organizer to update
        return (
            request.user.is_staff or 
            request.user == obj.organizer.user
        )

class EventViewSet(viewsets.ModelViewSet):
    """
    Viewset for handling event updates with granular control
    """
    queryset = Event.objects.all()
    serializer_class = EventUpdateSerializer
    permission_classes = [IsAuthenticated, EventUpdatePermission]

    def partial_update(self, request, *args, **kwargs):
        """
        Override partial_update to add custom validation and response
        """
        instance = self.get_object()
        
        # Create serializer with partial data
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        
        try:
            serializer.is_valid(raise_exception=True)
            
            # Additional custom validations
            if 'max_participants' in request.data:
                # Prevent reducing participants below current registrations
                current_registrations = EventRegistration.objects.filter(
                    event=instance, 
                    status='registered'
                ).count()
                
                new_max = serializer.validated_data.get('max_participants', instance.max_participants)
                
                if new_max is not None and new_max < current_registrations:
                    return Response({
                        'error': 'Cannot reduce max participants below current registered participants'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Save the updated event
            self.perform_update(serializer)
            
            return Response({
                'message': 'Event updated successfully', 
                'updated_data': serializer.data
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, EventUpdatePermission])
    def update_event_status(self, request, pk=None):
        """
        Specific action to update event status with logging
        """
        event = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status:
            return Response({
                'error': 'Status is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log status change (optional)
        event.status = new_status
        event.save()
        
        return Response({
            'message': f'Event status updated to {new_status}',
            'new_status': new_status
        }, status=status.HTTP_200_OK)
        
# events/api_views.py
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
class DeleteCommentView(generics.DestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        comment_id = self.kwargs.get('comment_id')
        comment = get_object_or_404(Comment, id=comment_id)
        if comment.user != self.request.user.profile:
            raise PermissionDenied("You don't have permission to delete this comment")
        return comment

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'status': 'success',
            'message': 'Comment deleted successfully'
        }, status=status.HTTP_200_OK)