"""Public facing views for the main site."""
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

def index(request: HttpRequest) -> HttpResponse:
    """Display the landing page."""
    return render(request, 'public/index.html')

@require_http_methods(["GET"])
def about(request: HttpRequest) -> HttpResponse:
    """Display the about page."""
    return render(request, 'public/about.html')

@require_http_methods(["GET", "POST"])
def contact(request: HttpRequest) -> HttpResponse:
    """Handle contact form submissions."""
    if request.method == "POST":
        messages.success(request, 'Thank you for your message! We will get back to you soon.')
        return render(request, 'public/contact.html')
    
    return render(request, 'public/contact.html')