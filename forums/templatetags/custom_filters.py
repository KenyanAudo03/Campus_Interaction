from django.utils.timezone import now
from datetime import datetime
from django import template
import re
from django.utils.timezone import now
from datetime import timedelta
register = template.Library()

@register.filter
def short_timesince(value):
    if not isinstance(value, datetime):
        return value

    current_time = now()
    delta = current_time - value

    if delta.days > 365:
        return f"• {delta.days // 365} yr ago •"
    elif delta.days > 30:
        return f"• {delta.days // 30} mon ago •"
    elif delta.days > 0:
        return f"• {delta.days} day ago •"
    elif delta.seconds // 3600 > 0:
        return f"• {delta.seconds // 3600} h  ago •"
    elif delta.seconds // 60 > 0:
        return f"• {delta.seconds // 60} min ago •"
    else:
        return "• just now •"

@register.filter
def is_editable(value):
    """
    Returns True if the given datetime is within the last 30 minutes.
    """
    if not isinstance(value, datetime):
        return False
    
    current_time = now()
    delta = current_time - value
    return delta <= timedelta(minutes=30)