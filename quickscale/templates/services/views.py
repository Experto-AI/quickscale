from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction
from credits.models import CreditAccount, Service, ServiceUsage, InsufficientCreditsError
from .decorators import get_all_registered_services


@login_required
def service_list(request):
    """Display all available services for the user."""
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
    
    return render(request, 'services/service_list.html', context)


@login_required
def service_usage_form(request, service_id):
    """Display the service usage form with credit validation."""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    current_balance = credit_account.get_balance()
    
    # Get balance details for credit breakdown
    balance_details = credit_account.get_balance_by_type_available()
    
    # Calculate consumption preview
    consumption_preview = None
    credits_needed = 0
    
    if current_balance >= service.credit_cost:
        # Calculate how credits will be consumed
        subscription_available = balance_details['subscription']
        
        if service.credit_cost <= subscription_available:
            consumption_preview = {
                'type': 'subscription_only',
                'subscription_used': service.credit_cost,
                'payg_used': 0
            }
        elif subscription_available > 0:
            payg_needed = service.credit_cost - subscription_available
            consumption_preview = {
                'type': 'mixed',
                'subscription_used': subscription_available,
                'payg_used': payg_needed
            }
        else:
            consumption_preview = {
                'type': 'payg_only',
                'subscription_used': 0,
                'payg_used': service.credit_cost
            }
    else:
        # Calculate how many more credits are needed
        credits_needed = service.credit_cost - current_balance
    
    context = {
        'service': service,
        'current_balance': current_balance,
        'credit_account': credit_account,
        'balance_details': balance_details,
        'consumption_preview': consumption_preview,
        'credits_needed': credits_needed,
    }
    
    return render(request, 'services/service_usage_form.html', context)


@login_required
@require_http_methods(["POST"])
def use_service(request, service_id):
    """HTMX endpoint for service usage with credit consumption."""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    
    try:
        with transaction.atomic():
            # Get balance breakdown before consumption
            balance_before = credit_account.get_balance_by_type_available()
            
            # Consume credits using priority system
            credit_transaction = credit_account.consume_credits_with_priority(
                amount=service.credit_cost,
                description=f"Used service: {service.name}"
            )
            
            # Get balance breakdown after consumption
            balance_after = credit_account.get_balance_by_type_available()
            
            # Calculate what was consumed from each type
            subscription_consumed = balance_before['subscription'] - balance_after['subscription']
            payg_consumed = balance_before['pay_as_you_go'] - balance_after['pay_as_you_go']
            
            # Create service usage record
            service_usage = ServiceUsage.objects.create(
                user=request.user,
                service=service,
                credit_transaction=credit_transaction
            )
            
            # Create detailed success message
            consumption_details = []
            if subscription_consumed > 0:
                consumption_details.append(f"{subscription_consumed} subscription credits")
            if payg_consumed > 0:
                consumption_details.append(f"{payg_consumed} pay-as-you-go credits")
            
            consumption_msg = " + ".join(consumption_details) if consumption_details else f"{service.credit_cost} credits"
            
            # Return HTMX success response with template
            context = {
                'success': True,
                'message': f"Successfully used {service.name}! Consumed {consumption_msg}.",
                'remaining_balance': float(credit_account.get_available_balance()),
                'subscription_balance': float(balance_after['subscription']),
                'payg_balance': float(balance_after['pay_as_you_go']),
                'service_usage_id': service_usage.id
            }
            return render(request, 'services/service_usage_result.html', context)
            
    except InsufficientCreditsError:
        balance_breakdown = credit_account.get_balance_by_type_available()
        context = {
            'success': False,
            'error': f"Insufficient credits to use {service.name}. Required: {service.credit_cost} credits, Available: {balance_breakdown['total']} credits."
        }
        return render(request, 'services/service_usage_result.html', context)
    except Exception as e:
        context = {
            'success': False,
            'error': f"An error occurred while using {service.name}: {str(e)}"
        }
        return render(request, 'services/service_usage_result.html', context)


@login_required
@require_http_methods(["GET"])
def service_status_api(request, service_id):
    """API endpoint to get service status and user's ability to use it."""
    service = get_object_or_404(Service, id=service_id, is_active=True)
    credit_account = CreditAccount.get_or_create_for_user(request.user)
    
    # Get user's usage count for this service
    usage_count = ServiceUsage.objects.filter(
        user=request.user,
        service=service
    ).count()
    
    # Check if user has sufficient credits
    current_balance = credit_account.get_balance()
    has_sufficient_credits = current_balance >= service.credit_cost
    
    # Get registered services information
    registered_services = get_all_registered_services()
    is_registered = service.name in registered_services
    
    return JsonResponse({
        'service_id': service.id,
        'service_name': service.name,
        'service_description': service.description,
        'credit_cost': float(service.credit_cost),
        'user_usage_count': usage_count,
        'user_balance': float(current_balance),
        'has_sufficient_credits': has_sufficient_credits,
        'is_registered': is_registered,
        'service_class': registered_services.get(service.name, {}).get('class_name', 'Unknown') if is_registered else 'Not Registered'
    })