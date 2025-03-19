from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse

@login_required
@user_passes_test(lambda u: u.is_staff)
def index(request):
    return render(request, 'dashboard/index.html') 