from decimal import Decimal

from django import template

from core.currency import (
    convert_bdt_to_usd,
    convert_price,
    format_money,
)

register = template.Library()


@register.filter(name='money')
def money_filter(amount, currency='BDT'):
    """
    Format a BDT amount into active currency.
    Usage: {{ plan.price_monthly|money:CURRENT_CURRENCY }}
    """
    if not currency:
        currency = 'BDT'
    return format_money(amount, currency=str(currency).upper())


@register.filter(name='currency_val')
def currency_val_filter(amount, currency='BDT'):
    """
    Convert a BDT amount to target currency without symbol (raw decimal value).
    Usage: {{ plan.price_monthly|currency_val:CURRENT_CURRENCY }}
    """
    if not currency:
        currency = 'BDT'
    curr = str(currency).upper()
    val = convert_price(amount, target_currency=curr)
    if curr == 'USD':
        return f"{val:.2f}"
    else:
        try:
            d = Decimal(str(val))
            if d % 1 == 0:
                return f"{int(d)}"
            return f"{d:.2f}"
        except Exception:
            return str(val)


@register.filter(name='usd_val')
def usd_val_filter(amount):
    """Directly convert BDT to USD formatted as 0.00"""
    val = convert_bdt_to_usd(amount)
    return f"{val:.2f}"


@register.simple_tag(takes_context=True)
def price_display(context, amount_bdt, show_symbol=True):
    """
    Auto-render price based on CURRENT_CURRENCY in template context.
    Usage: {% price_display plan.price_monthly %}
    """
    currency = context.get('CURRENT_CURRENCY', 'BDT')
    return format_money(amount_bdt, currency=currency, show_symbol=show_symbol)
