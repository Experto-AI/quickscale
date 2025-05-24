from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db import transaction
from django.urls import reverse
from django.shortcuts import redirect
from .models import CreditAccount, CreditTransaction, Service, ServiceUsage, InsufficientCreditsError


@login_required
def credits_dashboard(request):
    """Display the user's credit dashboard with balance and recent transactions."""
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    current_balance = credit_account.get_balance()
    
    # Get recent 5 transactions
    recent_transactions = request.user.credit_transactions.all()[:5]
    
    context = {
        'credit_account': credit_account,
        'current_balance': current_balance,
        'recent_transactions': recent_transactions,
    }
    
    return render(request, 'credits/dashboard.html', context)


@login_required
@require_http_methods(["GET"])
def credit_balance_api(request):
    """API endpoint to get current credit balance."""
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    balance = credit_account.get_balance()
    
    return JsonResponse({
        'balance': float(balance),
        'formatted_balance': f"{balance} credits"
    })


@login_required
def services_list(request):
    """Display available services for credit consumption."""
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    current_balance = credit_account.get_balance()
    
    # Get all active services
    services = Service.objects.filter(is_active=True).order_by('name')
    
    # Add usage count for each service by the current user
    for service in services:
        service.user_usage_count = ServiceUsage.objects.filter(
            user=request.user,
            service=service
        ).count()
    
    context = {
        'services': services,
        'current_balance': current_balance,
        'credit_account': credit_account,
    }
    
    return render(request, 'credits/services.html', context)


@login_required
@require_http_methods(["POST"])
def use_service(request, service_id):
    """Use a service and consume credits."""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    
    try:
        with transaction.atomic():
            # Consume credits from user account
            credit_transaction = credit_account.consume_credits(
                amount=service.credit_cost,
                description=f"Used service: {service.name}"
            )
            
            # Create service usage record
            service_usage = ServiceUsage.objects.create(
                user=request.user,
                service=service,
                credit_transaction=credit_transaction
            )
            
            messages.success(
                request,
                f"Successfully used {service.name}! {service.credit_cost} credits consumed. "
                f"Remaining balance: {credit_account.get_balance()} credits."
            )
            
    except InsufficientCreditsError as e:
        messages.error(
            request,
            f"Insufficient credits to use {service.name}. "
            f"Required: {service.credit_cost} credits, "
            f"Available: {credit_account.get_balance()} credits."
        )
    except Exception as e:
        messages.error(
            request,
            f"An error occurred while using {service.name}: {str(e)}"
        )
    
    return redirect('credits:services')


@login_required
@require_http_methods(["GET"])
def service_usage_api(request, service_id):
    """API endpoint to get service usage information."""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    
    # Get user's usage count for this service
    usage_count = ServiceUsage.objects.filter(
        user=request.user,
        service=service
    ).count()
    
    # Check if user has sufficient credits
    has_sufficient_credits = credit_account.get_balance() >= service.credit_cost
    
    return JsonResponse({
        'service_id': service.id,
        'service_name': service.name,
        'credit_cost': float(service.credit_cost),
        'user_usage_count': usage_count,
        'user_balance': float(credit_account.get_balance()),
        'has_sufficient_credits': has_sufficient_credits,
        'formatted_cost': f"{service.credit_cost} credits"
    }) 