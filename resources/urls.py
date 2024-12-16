from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # URL for resource listing page, named 'resources'
    path('', views.resource_list, name='resources'),  # Name it 'resources'
    
    # URL for uploading a resource
    path('upload/', views.upload_resource, name='upload_resource'),
    
    # URL for filtering resources by category
    path('category/<str:category>/', views.resources_by_category, name='resources_by_category'),
]

# Add media URL for serving media files (like uploaded resources)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
