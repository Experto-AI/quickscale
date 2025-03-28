"""URL configuration for public facing pages."""
from django.urls import path

from . import views

app_name = 'public'

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
]