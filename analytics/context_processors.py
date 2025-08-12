"""
Context processor to make analytics configuration available in templates.
"""

from .models import AnalyticsConfiguration


def analytics_context(request):
    """
    Add analytics configuration to template context.
    """
    try:
        config = AnalyticsConfiguration.get_config()
        return {
            'analytics_enabled': config.enabled,
        }
    except:
        return {
            'analytics_enabled': False,
        }