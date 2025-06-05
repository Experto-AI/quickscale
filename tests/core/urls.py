from django.urls import path, include

urlpatterns = [
    path('accounts/', include('allauth.account.urls')),
    path('api/', include('api.urls')),
    path('dashboard/credits/', include('credits.urls')),
]