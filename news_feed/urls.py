from django.urls import path
from . import views

urlpatterns = [
    path('add-news/', views.add_news, name='add_news'),
    path('news/', views.news_list, name='news_list'),
]
