from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages

def index(request):
    """Landing page view"""
    return render(request, 'public/index.html')

@require_http_methods(["GET"])
def about(request):
    """About page view"""
    return render(request, 'public/about.html')

@require_http_methods(["GET", "POST"])
def contact(request):
    """Contact page view with form handling"""
    if request.method == "POST":
        # Here you would typically process the form data
        # For now, we'll just show a success message
        messages.success(request, 'Thank you for your message! We will get back to you soon.')
        return render(request, 'public/contact.html')
    return render(request, 'public/contact.html') 