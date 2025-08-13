"""
Wagtail admin integration for analytics dashboard.
"""

from django.urls import path, reverse
from django.utils import timezone
from datetime import timedelta, datetime
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel
from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, Avg, Q
from .models import (
    AnalyticsEvent, DailySummary, WeeklyReport,
    AnalyticsConfiguration, AnalyticsDebugLog
)
import json
import csv


@staff_member_required
def analytics_dashboard(request):
    """Main analytics dashboard view"""
    
    # Get date range from request or default to last 7 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=6)
    
    if request.GET.get('start_date'):
        try:
            start_date = datetime.strptime(request.GET['start_date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if request.GET.get('end_date'):
        try:
            end_date = datetime.strptime(request.GET['end_date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Get configuration
    config = AnalyticsConfiguration.get_config()
    
    # Get events for date range
    events = AnalyticsEvent.objects.filter(
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date,
        is_bot=False  # Exclude bots by default
    )
    
    # Calculate metrics
    metrics = {
        'total_page_views': events.filter(event_type='page_view').count(),
        'unique_visitors': events.values('session_id').distinct().count(),
        'total_searches': events.filter(event_type='search').count(),
        'error_count': events.filter(event_type='error').count(),
    }
    
    # Get top pages
    top_pages = events.filter(event_type='page_view').values('page_url').annotate(
        views=Count('id')
    ).order_by('-views')[:10]
    
    # Get top searches
    search_events = events.filter(event_type='search')
    top_searches = []
    for event in search_events[:100]:  # Sample first 100 for performance
        if event.event_data and 'query' in event.event_data:
            query = event.event_data['query']
            # Add to top searches (would need proper aggregation in production)
            top_searches.append(query)
    
    # Count search occurrences
    from collections import Counter
    search_counts = Counter(top_searches).most_common(10)
    
    # Get daily trend data for chart
    daily_data = []
    current = start_date
    while current <= end_date:
        day_events = events.filter(timestamp__date=current)
        daily_data.append({
            'date': current.strftime('%Y-%m-%d'),
            'page_views': day_events.filter(event_type='page_view').count(),
            'visitors': day_events.values('session_id').distinct().count(),
            'searches': day_events.filter(event_type='search').count(),
        })
        current += timedelta(days=1)
    
    # Get recent errors for debugging
    recent_errors = AnalyticsEvent.objects.filter(
        event_type='error',
        timestamp__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-timestamp')[:10]
    
    # Check system health
    system_health = {
        'analytics_enabled': config.enabled,
        'events_today': AnalyticsEvent.objects.filter(
            timestamp__date=timezone.now().date()
        ).count(),
        'failed_events': AnalyticsEvent.objects.filter(
            processing_status='failed',
            timestamp__gte=timezone.now() - timedelta(hours=24)
        ).count(),
        'debug_mode': config.debug_mode,
    }
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'metrics': metrics,
        'top_pages': top_pages,
        'top_searches': search_counts,
        'daily_data': json.dumps(daily_data),
        'recent_errors': recent_errors,
        'system_health': system_health,
        'config': config,
    }
    
    return render(request, 'analytics/dashboard.html', context)


@staff_member_required
def analytics_settings(request):
    """Analytics settings page"""
    config = AnalyticsConfiguration.get_config()
    
    if request.method == 'POST':
        # Update settings
        config.enabled = request.POST.get('enabled') == 'on'
        config.track_page_views = request.POST.get('track_page_views') == 'on'
        config.track_searches = request.POST.get('track_searches') == 'on'
        config.track_errors = request.POST.get('track_errors') == 'on'
        config.track_downloads = request.POST.get('track_downloads') == 'on'
        config.debug_mode = request.POST.get('debug_mode') == 'on'
        config.send_weekly_reports = request.POST.get('send_weekly_reports') == 'on'
        
        # Update numeric fields
        try:
            config.sampling_rate = float(request.POST.get('sampling_rate', 1.0))
            config.raw_event_retention_days = int(request.POST.get('raw_event_retention_days', 30))
            config.daily_summary_retention_days = int(request.POST.get('daily_summary_retention_days', 365))
        except (ValueError, TypeError):
            pass
        
        # Update email recipients
        recipients = request.POST.get('report_recipients', '').strip()
        if recipients:
            config.report_recipients = [email.strip() for email in recipients.split(',')]
        
        config.save()
        
        return redirect('analytics_dashboard')
    
    return render(request, 'analytics/settings.html', {'config': config})


@staff_member_required
def analytics_export(request):
    """Export analytics data as CSV"""
    
    # Get date range
    start_date = request.GET.get('start_date', (timezone.now() - timedelta(days=30)).date())
    end_date = request.GET.get('end_date', timezone.now().date())
    
    # Get events
    events = AnalyticsEvent.objects.filter(
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    ).order_by('timestamp')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="analytics_{start_date}_{end_date}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'Event Type', 'Page URL', 'User', 'Session ID',
        'IP Address', 'User Agent', 'Is Bot', 'Processing Status'
    ])
    
    for event in events:
        writer.writerow([
            event.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            event.event_type,
            event.page_url,
            event.user.username if event.user else 'Anonymous',
            event.session_id,
            event.ip_address,
            event.user_agent[:50],
            'Yes' if event.is_bot else 'No',
            event.processing_status
        ])
    
    return response


@staff_member_required
def analytics_debug(request):
    """Debug view for troubleshooting"""
    
    # Get recent debug logs
    debug_logs = AnalyticsDebugLog.objects.all()[:50]
    
    # Get failed events
    failed_events = AnalyticsEvent.objects.filter(
        processing_status='failed'
    ).order_by('-timestamp')[:20]
    
    # System checks
    checks = []
    
    # Check if analytics is working
    recent_events = AnalyticsEvent.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=1)
    ).count()
    
    checks.append({
        'name': 'Recent Events',
        'status': 'ok' if recent_events > 0 else 'warning',
        'message': f'{recent_events} events in last hour'
    })
    
    # Check error rate
    total_recent = AnalyticsEvent.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    failed_recent = AnalyticsEvent.objects.filter(
        timestamp__gte=timezone.now() - timedelta(hours=24),
        processing_status='failed'
    ).count()
    
    error_rate = (failed_recent / total_recent * 100) if total_recent > 0 else 0
    
    checks.append({
        'name': 'Error Rate',
        'status': 'ok' if error_rate < 5 else 'warning' if error_rate < 20 else 'error',
        'message': f'{error_rate:.1f}% ({failed_recent}/{total_recent})'
    })
    
    context = {
        'debug_logs': debug_logs,
        'failed_events': failed_events,
        'checks': checks,
    }
    
    return render(request, 'analytics/debug.html', context)


@staff_member_required
def analytics_advanced(request):
    """Advanced analytics dashboard view"""
    return render(request, 'analytics/advanced_dashboard.html')


# Register with Wagtail admin
@hooks.register('register_admin_urls')
def register_analytics_urls():
    return [
        path('analytics/', analytics_dashboard, name='analytics_dashboard'),
        path('analytics/advanced/', analytics_advanced, name='analytics_advanced'),
        path('analytics/settings/', analytics_settings, name='analytics_settings'),
        path('analytics/export/', analytics_export, name='analytics_export'),
        path('analytics/debug/', analytics_debug, name='analytics_debug'),
    ]


# API URLs
@hooks.register('register_admin_urls')  
def register_analytics_api_urls():
    from .api_views import (
        track_custom_events, ab_test_variant, ab_test_conversion,
        user_journey_analysis, conversion_funnel_analysis, ab_test_results
    )
    
    return [
        path('api/analytics/events/', track_custom_events, name='api_analytics_events'),
        path('api/analytics/ab-test/<str:test_name>/variant/', ab_test_variant, name='api_ab_test_variant'),
        path('api/analytics/ab-test/<str:test_name>/conversion/', ab_test_conversion, name='api_ab_test_conversion'),
        path('api/analytics/journeys/', user_journey_analysis, name='api_user_journeys'),
        path('api/analytics/funnel/<str:funnel_name>/', conversion_funnel_analysis, name='api_conversion_funnel'),
        path('api/analytics/ab-test/<str:test_name>/results/', ab_test_results, name='api_ab_test_results'),
    ]


@hooks.register('register_admin_menu_item')
def register_analytics_menu():
    from wagtail.admin.menu import SubmenuMenuItem, MenuItem, Menu
    
    # Create a Menu object with the menu items
    analytics_menu = Menu(items=[
        MenuItem('Dashboard', reverse('analytics_dashboard'), icon_name='chart-bar'),
        MenuItem('Advanced', reverse('analytics_advanced'), icon_name='chart-line'),
        MenuItem('Settings', reverse('analytics_settings'), icon_name='cog'),
        MenuItem('Debug', reverse('analytics_debug'), icon_name='help'),
    ])
    
    return SubmenuMenuItem(
        'Analytics',
        analytics_menu,
        icon_name='chart-line',
        order=1000
    )