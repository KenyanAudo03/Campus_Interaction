from django.urls import path
from . import views

app_name = "maps"
urlpatterns = [
    path('', views.maps, name='maps'),
    path('save-search/', views.save_search, name='save_search'),
    path('recent-searches/', views.recent_searches, name='recent_searches'),
]