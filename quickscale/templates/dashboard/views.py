"""Staff dashboard views."""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

@login_required
@user_passes_test(lambda u: u.is_staff)
def index(request: HttpRequest) -> HttpResponse:
    """Display the staff dashboard."""
    return render(request, 'dashboard/index.html')