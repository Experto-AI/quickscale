"""Template tags for Stripe integration."""
from django import template
from django.utils.safestring import mark_safe
from django.template.defaultfilters import floatformat

register = template.Library()


@register.filter
def format_stripe_price(price):
    """Format a Stripe price object for display.
    
    Handles both attribute-based objects (original Stripe SDK) and 
    dictionary-style objects (newer Stripe API versions).
    
    Args:
        price: A Stripe price object (either attribute or dict style)
        
    Returns:
        A formatted price string with currency symbol
    """
    if not price:
        return 'No price'
    
    try:
        # Check if we're dealing with dict-style access (new API)
        if isinstance(price, dict):
            # Empty dict should be considered invalid
            if not price:
                return 'Invalid price'
                
            # Get amount - try decimal first for precision
            if 'unit_amount_decimal' in price:
                amount = float(price['unit_amount_decimal']) / 100
            elif 'unit_amount' in price:
                amount = float(price['unit_amount']) / 100
            else:
                return 'Invalid price'
            
            currency = price.get('currency', 'USD').upper()
            
            # Check for recurring pricing
            interval_text = ""
            if 'recurring' in price and price['recurring']:
                interval = price['recurring'].get('interval', '')
                interval_count = price['recurring'].get('interval_count', 1)
                
                if interval:
                    if interval_count == 1:
                        interval_text = f"/{interval}"
                    else:
                        interval_text = f"/{interval_count} {interval}s"
        
        # Original attribute-style access (old SDK)
        else:
            # Ensure unit_amount exists
            if not hasattr(price, 'unit_amount'):
                return 'Invalid price'
                
            # Stripe stores amounts in cents
            amount = price.unit_amount / 100.0
            currency = price.currency.upper()
            
            # Check for recurring pricing
            interval_text = ""
            if hasattr(price, 'recurring') and price.recurring:
                interval = getattr(price.recurring, 'interval', '')
                interval_count = getattr(price.recurring, 'interval_count', 1)
                
                if interval:
                    if interval_count == 1:
                        interval_text = f"/{interval}"
                    else:
                        interval_text = f"/{interval_count} {interval}s"
        
        # Format based on common currencies
        currency_symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'AUD': 'A$',
            'CAD': 'C$',
            'CHF': 'CHF'
        }
        
        symbol = currency_symbols.get(currency, currency)
        
        # Format the price with correct decimal places
        if currency == 'JPY':  # JPY doesn't use decimal places
            formatted_amount = floatformat(amount, 0)
        else:
            formatted_amount = floatformat(amount, 2)
            
        # Combine everything
        return mark_safe(f"{symbol}{formatted_amount}{interval_text}")
        
    except (AttributeError, KeyError, ValueError, TypeError):
        # Return a simple fallback if anything goes wrong
        return "Price unavailable"


@register.filter
def get_stripe_product_name(product):
    """Safely get the name of a Stripe product.
    
    Args:
        product: A Stripe product object
        
    Returns:
        The product name or a default string
    """
    if not product:
        return 'Unknown Product'
    
    # Check if we're dealing with dict-style access
    if isinstance(product, dict):
        # Empty dict should be considered unnamed
        if not product:
            return 'Unnamed Product'
        return product.get('name', 'Unnamed Product')
    
    # Original attribute-style access
    return getattr(product, 'name', 'Unnamed Product')


@register.filter
def get_stripe_product_status(product):
    """Safely get the status of a Stripe product.
    
    Args:
        product: A Stripe product object
        
    Returns:
        The product status or a default string
    """
    if not product:
        return 'unknown'
    
    # Check if we're dealing with dict-style access
    if isinstance(product, dict):
        # Empty dict should return inactive
        if not product:
            return 'inactive'
        return 'active' if product.get('active', False) else 'inactive'
    
    # Original attribute-style access
    return 'active' if getattr(product, 'active', False) else 'inactive'


@register.filter
def get_stripe_price(product, currency='usd'):
    """Find a price object by currency.
    
    Args:
        product: A Stripe product object
        currency: The currency code to find (default: usd)
        
    Returns:
        The matching price object or None
    """
    if not product:
        return None
    
    # Check if we're dealing with dict-style access
    if isinstance(product, dict):
        prices = product.get('prices', {}).get('data', [])
        
        # Find price matching the requested currency
        for price in prices:
            price_currency = price.get('currency', '').lower()
            if price_currency == currency.lower():
                return price
        
        # Return first price as fallback
        return prices[0] if prices else None
    
    # Original attribute-style access
    if not hasattr(product, 'prices') or not hasattr(product.prices, 'data'):
        return None
    
    # Find price matching the requested currency
    for price in product.prices.data:
        if price.currency.lower() == currency.lower():
            return price
    
    # Return first price as fallback
    return product.prices.data[0] if product.prices.data else None 