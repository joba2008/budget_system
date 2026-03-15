import json

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Get a value from a dictionary by key."""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def format_money(value):
    """Format a number as money display."""
    if value is None:
        return ''
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)
    if abs(val) >= 1_000_000:
        return f'${val/1_000_000:.2f}M'
    elif abs(val) >= 1_000:
        return f'${val:,.0f}'
    else:
        return f'${val:,.2f}'


@register.filter
def format_number(value):
    """Format a number with commas."""
    if value is None:
        return ''
    try:
        val = float(value)
        return f'{val:,.2f}'
    except (ValueError, TypeError):
        return str(value)


@register.filter(is_safe=True)
def to_json(value):
    """Serialize a value to JSON for use in templates."""
    return json.dumps(value)
