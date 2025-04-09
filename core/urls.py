from django.urls import path, include

urlpatterns = [
    path('accounts/', include('allauth.account.urls')),
] 