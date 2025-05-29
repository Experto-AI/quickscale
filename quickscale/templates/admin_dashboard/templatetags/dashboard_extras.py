"""Template tags for dashboard app."""

from django import template
from decimal import Decimal

register = template.Library()


@register.filter
def sub(value, arg):
    """Subtract arg from value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def multiply(value, arg):
    """Multiply value by arg."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def divide(value, arg):
    """Divide value by arg."""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def cost_per_credit(price, credits):
    """Calculate cost per credit in cents."""
    try:
        price_float = float(price)
        credits_int = int(credits)
        if credits_int == 0:
            return 0
        # Convert to cents and round to 2 decimal places
        return round((price_float / credits_int) * 100, 2)
    except (ValueError, TypeError):
        return 0


@register.filter
def savings_per_credit(basic_price, basic_credits, pro_price, pro_credits):
    """Calculate savings per credit between two plans."""
    try:
        basic_cost = cost_per_credit(basic_price, basic_credits)
        pro_cost = cost_per_credit(pro_price, pro_credits)
        return round(basic_cost - pro_cost, 2)
    except (ValueError, TypeError):
        return 0 