from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import CreditAccount, CreditTransaction


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