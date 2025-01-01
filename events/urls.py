# events/urls.py
from django.urls import path, include
from rest_framework_nested import routers
from . import api_views
from .views import (
    EventListView,
    EventDetailView,
    MultiStepEventCreateView,
    CommentCreateView,
    CommentLikeToggleView,
    EventDeleteView,
    CampusAutocompleteView,
    LoadMoreCommentsView,
    EventUpdateView,
    # update_event,
    cancel_registration,
    event_status_view,
    register_event,
)

# Create a router for the main viewset
router = routers.DefaultRouter()
router.register(r'events', api_views.EventViewSet, basename='event')

# Create a nested router for comments
event_router = routers.NestedDefaultRouter(router, r'events', lookup='event')
event_router.register(r'comments', api_views.CommentViewSet, basename='event-comments')

app_name = 'events'

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    path('api/', include(event_router.urls)),
    path('api/comments/<int:comment_id>/delete/', api_views.DeleteCommentView.as_view(), name='delete_comment'),
    path('api/event/<int:event_id>/status/', event_status_view, name='event_status'),
    path('api/events/<int:event_id>/update/', EventUpdateView.as_view(), name='update_event'),

    # Main event URLs
    path('', EventListView.as_view(), name='event_list'),
    path('<int:event_id>/', EventDetailView.as_view(), name='event_detail'),
    path('create/', MultiStepEventCreateView.as_view(), name='create_event'),
    path('<int:event_id>/delete/', EventDeleteView.as_view(), name='delete_event'),

    # Comment URLs
    path('<int:event_id>/comment/', CommentCreateView.as_view(), name='add_comment'),
    path('comment/<int:comment_id>/like/', CommentLikeToggleView.as_view(), name='toggle_comment_like'),
    path('<int:event_id>/comments/', LoadMoreCommentsView.as_view(), name='load_more_comments'),

    # Utility URLs
    path('university/autocomplete/', CampusAutocompleteView.as_view(), name='university_autocomplete'),
    path('select2/', include('django_select2.urls')),

    # Registration URLs
    path('event/<int:event_id>/register/', register_event, name='event_register'),
    path('event/<int:event_id>/cancel/', cancel_registration, name='event_cancel_registration'),
]