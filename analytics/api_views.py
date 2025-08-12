"""
Advanced analytics API views for Stage 3 features.
Handles custom event tracking, A/B testing, and user journey analysis.
"""

import json
import logging
from datetime import timedelta
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models, transaction
from django.db.models import Count, Avg, Q, F
from .models import AnalyticsEvent, AnalyticsConfiguration
from .models_advanced import (
    UserJourney, ABTest, ABTestParticipation, 
    CustomEvent, ConversionFunnel, UserSegment
)
from .utils import get_client_ip, is_bot, sanitize_url
import uuid

logger = logging.getLogger('analytics')


@csrf_exempt
@require_http_methods(["POST"])
def track_custom_events(request):
    """
    API endpoint for bulk custom event tracking from JavaScript SDK.
    
    Payload format:
    {
        "events": [
            {
                "name": "button_click",
                "category": "interaction",
                "properties": {...},
                "value": 10.0,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        ],
        "session_id": "uuid",
        "user_id": 123
    }
    """
    try:
        # Check if analytics is enabled
        config = AnalyticsConfiguration.get_config()
        if not config.enabled:
            return JsonResponse({'success': False, 'error': 'Analytics disabled'})
        
        # Parse request body
        try:
            data = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'success': False, 'error': 'Invalid JSON'})
        
        events = data.get('events', [])
        session_id = data.get('session_id', '')
        user_id = data.get('user_id')
        
        if not events:
            return JsonResponse({'success': False, 'error': 'No events provided'})
        
        # Process events
        created_events = []
        errors = []
        
        with transaction.atomic():
            for event_data in events[:50]:  # Limit to 50 events per request
                try:
                    # Extract event data
                    name = event_data.get('name', '')[:100]
                    category = event_data.get('category', 'custom')[:50]
                    properties = event_data.get('properties', {})
                    value = event_data.get('value')
                    timestamp_str = event_data.get('timestamp')
                    
                    # Parse timestamp
                    if timestamp_str:
                        try:
                            timestamp = timezone.datetime.fromisoformat(
                                timestamp_str.replace('Z', '+00:00')
                            )
                        except ValueError:
                            timestamp = timezone.now()
                    else:
                        timestamp = timezone.now()
                    
                    # Create custom event
                    event = CustomEvent.objects.create(
                        name=name,
                        category=category,
                        session_id=session_id,
                        user_id=user_id if user_id else None,
                        timestamp=timestamp,
                        properties=properties,
                        value=value,
                        page_url=sanitize_url(event_data.get('page_url', '')),
                        referrer_url=sanitize_url(event_data.get('referrer_url', '')),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                        ip_address=get_client_ip(request)
                    )
                    
                    created_events.append(event.pk)
                    
                    # Update user journey if this is a page view
                    if name == 'page_view' and session_id:
                        update_user_journey(session_id, user_id, event_data, request)
                    
                    # Check for conversion goals
                    if name == 'conversion_goal':
                        handle_conversion_goal(session_id, event_data)
                    
                except Exception as e:
                    logger.error(f"Error processing custom event: {e}")
                    errors.append(str(e))
        
        # Process events asynchronously if needed
        if created_events:
            # Mark events for processing
            CustomEvent.objects.filter(pk__in=created_events).update(processed=True)
        
        return JsonResponse({
            'success': True,
            'events_created': len(created_events),
            'errors': errors
        })
        
    except Exception as e:
        logger.error(f"Custom event tracking error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': 'Internal server error'})


@csrf_exempt
@require_http_methods(["POST"])
def ab_test_variant(request, test_name):
    """
    Get A/B test variant assignment for a session.
    
    POST /api/analytics/ab-test/<test_name>/variant/
    Body: {"session_id": "uuid", "user_id": 123}
    """
    try:
        config = AnalyticsConfiguration.get_config()
        if not config.enabled:
            return JsonResponse({'variant': None})
        
        # Parse request
        data = json.loads(request.body.decode('utf-8'))
        session_id = data.get('session_id')
        user_id = data.get('user_id')
        
        if not session_id:
            return JsonResponse({'error': 'session_id required'}, status=400)
        
        # Get test
        try:
            test = ABTest.objects.get(name=test_name, is_active=True)
        except ABTest.DoesNotExist:
            return JsonResponse({'variant': None})
        
        # Check if session is already in test
        try:
            participation = ABTestParticipation.objects.get(
                test=test,
                session_id=session_id
            )
            return JsonResponse({'variant': participation.variant})
        except ABTestParticipation.DoesNotExist:
            pass
        
        # Assign new variant
        variant = test.get_variant_for_session(session_id)
        
        if variant:
            participation = test.record_participation(session_id, variant)
            if user_id:
                participation.user_id = user_id
                participation.save(update_fields=['user'])
            
            return JsonResponse({'variant': variant})
        
        return JsonResponse({'variant': None})
        
    except Exception as e:
        logger.error(f"A/B test variant error: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


@csrf_exempt  
@require_http_methods(["POST"])
def ab_test_conversion(request, test_name):
    """
    Record A/B test conversion.
    
    POST /api/analytics/ab-test/<test_name>/conversion/
    Body: {"session_id": "uuid", "goal": "signup", "value": 10.0}
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        session_id = data.get('session_id')
        goal = data.get('goal')
        value = data.get('value')
        
        if not session_id:
            return JsonResponse({'error': 'session_id required'}, status=400)
        
        # Get test
        try:
            test = ABTest.objects.get(name=test_name, is_active=True)
        except ABTest.DoesNotExist:
            return JsonResponse({'error': 'Test not found'}, status=404)
        
        # Record conversion
        test.record_conversion(session_id, goal)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"A/B test conversion error: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


@staff_member_required
def user_journey_analysis(request):
    """
    API for user journey analysis data.
    Returns journey statistics and common paths.
    """
    try:
        # Get date range
        days = int(request.GET.get('days', 7))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get journeys
        journeys = UserJourney.objects.filter(
            start_time__gte=start_date
        )
        
        # Calculate metrics
        total_journeys = journeys.count()
        avg_pages = journeys.aggregate(Avg('page_count'))['page_count__avg'] or 0
        avg_duration = journeys.aggregate(Avg('duration_seconds'))['duration_seconds__avg'] or 0
        bounce_rate = journeys.filter(is_bounce=True).count() / total_journeys * 100 if total_journeys > 0 else 0
        
        # Top entry pages
        entry_pages = journeys.values('entry_page').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Top exit pages
        exit_pages = journeys.values('exit_page').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Common paths (simplified)
        common_paths = []
        for journey in journeys.filter(page_count__gte=2, page_count__lte=5)[:100]:
            if journey.page_path:
                path_key = ' → '.join(journey.page_path[:3])  # First 3 pages
                common_paths.append(path_key)
        
        # Count path frequency
        from collections import Counter
        path_counts = Counter(common_paths).most_common(10)
        
        # Conversion goals
        conversions = journeys.exclude(completed_goal='').values(
            'completed_goal'
        ).annotate(count=Count('id')).order_by('-count')
        
        return JsonResponse({
            'metrics': {
                'total_journeys': total_journeys,
                'avg_pages_per_journey': round(avg_pages, 1),
                'avg_duration_minutes': round(avg_duration / 60, 1),
                'bounce_rate_percent': round(bounce_rate, 1)
            },
            'entry_pages': list(entry_pages),
            'exit_pages': list(exit_pages),
            'common_paths': [{'path': path, 'count': count} for path, count in path_counts],
            'conversions': list(conversions)
        })
        
    except Exception as e:
        logger.error(f"Journey analysis error: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


@staff_member_required
def conversion_funnel_analysis(request, funnel_name):
    """
    Analyze conversion funnel performance.
    """
    try:
        funnel = get_object_or_404(ConversionFunnel, name=funnel_name, is_active=True)
        
        # Get time range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Analyze funnel steps
        steps_analysis = []
        
        for i, step in enumerate(funnel.steps):
            step_name = step.get('name', f'Step {i+1}')
            step_events = CustomEvent.objects.filter(
                name=step.get('event_name'),
                timestamp__gte=start_date
            )
            
            steps_analysis.append({
                'step_number': i + 1,
                'step_name': step_name,
                'total_users': step_events.values('session_id').distinct().count(),
                'conversion_rate': 0,  # Calculate relative to previous step
            })
        
        # Calculate conversion rates
        for i in range(1, len(steps_analysis)):
            prev_users = steps_analysis[i-1]['total_users']
            curr_users = steps_analysis[i]['total_users']
            
            if prev_users > 0:
                steps_analysis[i]['conversion_rate'] = round(
                    (curr_users / prev_users) * 100, 1
                )
        
        return JsonResponse({
            'funnel': {
                'name': funnel.name,
                'description': funnel.description,
                'overall_conversion_rate': funnel.conversion_rate
            },
            'steps': steps_analysis
        })
        
    except Exception as e:
        logger.error(f"Funnel analysis error: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


@staff_member_required
def ab_test_results(request, test_name):
    """
    Get A/B test results and statistical analysis.
    """
    try:
        test = get_object_or_404(ABTest, name=test_name)
        
        # Get participation data
        participants = ABTestParticipation.objects.filter(test=test)
        
        # Calculate results per variant
        results = {}
        for variant_name in test.variants.keys():
            variant_participants = participants.filter(variant=variant_name)
            variant_conversions = variant_participants.filter(converted=True)
            
            total = variant_participants.count()
            conversions = variant_conversions.count()
            conversion_rate = (conversions / total * 100) if total > 0 else 0
            
            results[variant_name] = {
                'participants': total,
                'conversions': conversions,
                'conversion_rate': round(conversion_rate, 2),
                'avg_value': variant_conversions.aggregate(
                    avg=Avg('conversion_value')
                )['avg'] or 0
            }
        
        return JsonResponse({
            'test': {
                'name': test.name,
                'description': test.description,
                'is_active': test.is_active,
                'total_participants': test.total_participants
            },
            'results': results
        })
        
    except Exception as e:
        logger.error(f"A/B test results error: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


# Helper functions

def update_user_journey(session_id, user_id, event_data, request):
    """Update or create user journey for a session."""
    try:
        page_url = event_data.get('properties', {}).get('url', '')
        
        # Get or create journey
        journey, created = UserJourney.objects.get_or_create(
            session_id=session_id,
            defaults={
                'user_id': user_id if user_id else None,
                'start_time': timezone.now(),
                'entry_page': page_url,
                'referrer_domain': extract_domain(
                    event_data.get('properties', {}).get('referrer', '')
                ),
                'device_type': detect_device_type(request.META.get('HTTP_USER_AGENT', ''))
            }
        )
        
        # Add page to journey path
        if page_url:
            journey.add_page_visit(page_url)
            journey.end_time = timezone.now()
            journey.calculate_duration()
            journey.total_events = F('total_events') + 1
            journey.save(update_fields=['end_time', 'total_events'])
            
    except Exception as e:
        logger.error(f"Journey update error: {e}")


def handle_conversion_goal(session_id, event_data):
    """Handle conversion goal completion."""
    try:
        goal_name = event_data.get('properties', {}).get('goal_name')
        goal_value = event_data.get('properties', {}).get('goal_value')
        
        if not goal_name:
            return
        
        # Update journey
        try:
            journey = UserJourney.objects.get(session_id=session_id)
            journey.mark_goal_completed(goal_name, goal_value)
        except UserJourney.DoesNotExist:
            pass
        
        # Check A/B tests for conversion
        participations = ABTestParticipation.objects.filter(
            session_id=session_id,
            test__is_active=True
        )
        
        for participation in participations:
            if (not participation.converted and 
                (participation.test.primary_goal == goal_name or 
                 goal_name in participation.test.secondary_goals)):
                participation.mark_converted(goal_name, goal_value)
                participation.test.record_conversion(session_id, goal_name)
                
    except Exception as e:
        logger.error(f"Conversion handling error: {e}")


def extract_domain(url):
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except:
        return ''


def detect_device_type(user_agent):
    """Detect device type from user agent."""
    user_agent_lower = user_agent.lower()
    
    if any(mobile in user_agent_lower for mobile in ['mobile', 'android', 'iphone', 'ipod']):
        return 'mobile'
    elif 'ipad' in user_agent_lower or 'tablet' in user_agent_lower:
        return 'tablet'
    else:
        return 'desktop'