import json
from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse

from credits.models import CreditAccount, CreditTransaction, Service, ServiceUsage
from credits.models import Payment, UserSubscription
from users.models import CustomUser


@login_required
@user_passes_test(lambda u: u.is_staff)
def analytics_dashboard(request):
    """Display the analytics dashboard with key business metrics."""
    # Calculate basic metrics (total users, revenue, active subscriptions)
    total_users = CustomUser.objects.count()
    
    # Total revenue from successful payments
    total_revenue = Payment.objects.filter(status='succeeded').aggregate(Sum('amount'))['amount__sum'] or Decimal(0)
    
    # Active subscriptions count
    active_subscriptions = UserSubscription.objects.filter(status='active').count()

    # Calculate monthly revenue for the last 12 months
    monthly_revenue = []
    current_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    for i in range(12):
        # Calculate proper calendar months
        if i == 0:
            start_of_month = current_date
        else:
            # Go back proper calendar months
            year = current_date.year
            month = current_date.month - i
            while month <= 0:
                month += 12
                year -= 1
            start_of_month = current_date.replace(year=year, month=month)
        
        # Calculate end of month
        if start_of_month.month == 12:
            end_of_month = start_of_month.replace(year=start_of_month.year + 1, month=1) - timedelta(microseconds=1)
        else:
            end_of_month = start_of_month.replace(month=start_of_month.month + 1) - timedelta(microseconds=1)

        month_total = Payment.objects.filter(
            status='succeeded',
            created_at__gte=start_of_month,
            created_at__lte=end_of_month
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal(0)

        monthly_revenue.append({
            'month': start_of_month.strftime('%b %Y'),
            'revenue': float(month_total)  # Convert Decimal to float for JSON serialization
        })
    
    monthly_revenue.reverse()  # Show oldest first

    # Service usage statistics
    all_services = Service.objects.all().order_by('name')
    service_stats = []
    for service in all_services:
        total_credits_consumed = ServiceUsage.objects.filter(service=service).aggregate(Sum('credit_transaction__amount'))['credit_transaction__amount__sum'] or Decimal(0)
        unique_users_count = ServiceUsage.objects.filter(service=service).values('user').distinct().count()
        service_stats.append({
            'name': service.name,
            'description': service.description,
            'credit_cost': float(service.credit_cost),  # Convert Decimal to float
            'total_credits_consumed': float(abs(total_credits_consumed)),  # Convert Decimal to float and use absolute value
            'unique_users_count': unique_users_count,
            'is_active': service.is_active,
        })
    
    context = {
        'total_users': total_users,
        'total_revenue': float(total_revenue),  # Convert Decimal to float for template compatibility
        'active_subscriptions': active_subscriptions,
        'service_stats': service_stats,
        'monthly_revenue': monthly_revenue,
        'monthly_revenue_json': json.dumps(monthly_revenue),  # JSON string for Alpine.js
    }

    return render(request, 'admin_dashboard/analytics_dashboard.html', context)


def index(request):
    """Dummy admin dashboard index view for tests."""
    return HttpResponse("Test Admin Dashboard Index")


@login_required
def user_dashboard(request):
    """Dummy user dashboard view for tests."""
    return HttpResponse("Test User Dashboard") 