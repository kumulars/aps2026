"""
Analytics middleware with comprehensive error handling and fallback mechanisms.
Tracks page views, errors, and performance metrics without affecting site performance.
"""

import uuid
import time
import json
import logging
import traceback
from django.utils import timezone
from django.shortcuts import render
from django.http import HttpResponse
from .models import AnalyticsEvent, AnalyticsConfiguration, AnalyticsDebugLog
from .models_advanced import UserJourney, CustomEvent
from .utils import is_bot, get_client_ip, sanitize_url

logger = logging.getLogger('analytics')


class AnalyticsMiddleware:
    """
    Main analytics tracking middleware with error isolation and recovery.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.config = None
        self.last_config_check = None
        self.config_check_interval = 60  # Reload config every 60 seconds
        
    def __call__(self, request):
        """
        Process request with comprehensive error handling.
        Analytics errors never affect the main site.
        """
        # Start timing for performance metrics
        start_time = time.time()
        
        # Initialize session tracking
        self._ensure_session(request)
        
        # Track request start (non-blocking)
        try:
            if self._should_track(request):
                self._track_request_start(request)
        except Exception as e:
            self._log_error('track_request_start', e, request)
        
        # Process the request normally
        response = None
        error_occurred = False
        
        try:
            response = self.get_response(request)
        except Exception as e:
            error_occurred = True
            # Track the error but let Django handle it
            self._track_error(request, e)
            raise
        finally:
            # Track request completion (non-blocking)
            try:
                if self._should_track(request) and response:
                    elapsed_time = int((time.time() - start_time) * 1000)
                    self._track_request_complete(request, response, elapsed_time)
            except Exception as e:
                self._log_error('track_request_complete', e, request)
        
        return response
    
    def _ensure_session(self, request):
        """Ensure session exists for tracking"""
        try:
            if not request.session.session_key:
                request.session.save()
            
            # Set analytics session ID if not present
            if 'analytics_session_id' not in request.session:
                request.session['analytics_session_id'] = str(uuid.uuid4())
                request.session['analytics_session_start'] = timezone.now().isoformat()
        except Exception as e:
            # Session tracking failure is non-critical
            logger.debug(f"Session initialization failed: {e}")
    
    def _should_track(self, request):
        """Determine if request should be tracked"""
        try:
            # Reload config if needed
            if self._should_reload_config():
                self.config = AnalyticsConfiguration.get_config()
                self.last_config_check = time.time()
            
            # Check if analytics is enabled
            if not self.config or not self.config.enabled:
                return False
            
            # Skip admin and static files
            path = request.path
            if any(path.startswith(skip) for skip in ['/admin/', '/static/', '/media/', '/__debug__/']):
                return False
            
            # Skip certain file extensions
            if any(path.endswith(ext) for ext in ['.js', '.css', '.png', '.jpg', '.ico', '.xml', '.txt']):
                return False
            
            # Check sampling rate
            if self.config.sampling_rate < 1.0:
                import random
                if random.random() > self.config.sampling_rate:
                    return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Should track check failed: {e}")
            return False  # Default to not tracking on error
    
    def _should_reload_config(self):
        """Check if config should be reloaded"""
        if not self.config or not self.last_config_check:
            return True
        return (time.time() - self.last_config_check) > self.config_check_interval
    
    def _track_request_start(self, request):
        """Track the start of a request"""
        try:
            # Detect bots
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            is_bot_request = is_bot(user_agent, self.config.bot_user_agents if self.config else [])
            
            # Don't track bot requests unless configured to
            if is_bot_request and self.config and not self.config.debug_mode:
                return
            
            # Store tracking data in request for later use
            request._analytics_data = {
                'start_time': time.time(),
                'is_bot': is_bot_request,
                'session_id': request.session.get('analytics_session_id', ''),
                'user_agent': user_agent,
            }
            
        except Exception as e:
            logger.debug(f"Request start tracking failed: {e}")
    
    def _track_request_complete(self, request, response, elapsed_time):
        """Track request completion with page view event"""
        try:
            # Skip if no tracking data
            if not hasattr(request, '_analytics_data'):
                return
            
            # Skip unsuccessful responses in production
            if response.status_code >= 400 and not self.config.debug_mode:
                if response.status_code == 404 and self.config.track_errors:
                    self._track_404(request)
                return
            
            # Create page view event
            event_data = {
                'status_code': response.status_code,
                'method': request.method,
                'is_ajax': request.headers.get('X-Requested-With') == 'XMLHttpRequest',
            }
            
            # Add search tracking if present
            if request.GET.get('search') or request.GET.get('q'):
                search_query = request.GET.get('search') or request.GET.get('q')
                if self.config.track_searches:
                    self._track_search(request, search_query)
            
            # Create the event
            AnalyticsEvent.objects.create(
                event_type='page_view',
                timestamp=timezone.now(),
                user=request.user if request.user.is_authenticated else None,
                session_id=request._analytics_data.get('session_id', ''),
                ip_address=get_client_ip(request),
                user_agent=request._analytics_data.get('user_agent', ''),
                page_url=sanitize_url(request.build_absolute_uri()),
                referrer_url=request.META.get('HTTP_REFERER', '')[:500],
                event_data=event_data,
                page_load_time=elapsed_time,
                is_bot=request._analytics_data.get('is_bot', False),
                processing_status='processed'
            )
            
            # Update user journey
            self._update_user_journey(request, elapsed_time)
            
        except Exception as e:
            self._log_error('track_request_complete', e, request)
    
    def _track_search(self, request, query):
        """Track search queries"""
        try:
            AnalyticsEvent.objects.create(
                event_type='search',
                timestamp=timezone.now(),
                user=request.user if request.user.is_authenticated else None,
                session_id=request.session.get('analytics_session_id', ''),
                page_url=sanitize_url(request.build_absolute_uri()),
                event_data={
                    'query': query[:200],  # Limit query length
                    'results_page': request.GET.get('page', 1),
                    'filters': {
                        k: v for k, v in request.GET.items() 
                        if k not in ['search', 'q', 'page']
                    }
                },
                processing_status='processed'
            )
        except Exception as e:
            logger.debug(f"Search tracking failed: {e}")
    
    def _track_404(self, request):
        """Track 404 errors"""
        try:
            AnalyticsEvent.objects.create(
                event_type='error',
                timestamp=timezone.now(),
                user=request.user if request.user.is_authenticated else None,
                session_id=request.session.get('analytics_session_id', ''),
                page_url=sanitize_url(request.build_absolute_uri()),
                referrer_url=request.META.get('HTTP_REFERER', '')[:500],
                event_data={
                    'error_type': '404',
                    'path': request.path,
                },
                processing_status='processed'
            )
        except Exception as e:
            logger.debug(f"404 tracking failed: {e}")
    
    def _track_error(self, request, exception):
        """Track application errors"""
        try:
            if self.config and self.config.track_errors:
                AnalyticsEvent.objects.create(
                    event_type='error',
                    timestamp=timezone.now(),
                    user=request.user if request.user.is_authenticated else None,
                    session_id=request.session.get('analytics_session_id', ''),
                    page_url=sanitize_url(request.build_absolute_uri()),
                    event_data={
                        'error_type': type(exception).__name__,
                        'error_message': str(exception)[:500],
                        'traceback': traceback.format_exc()[:2000] if self.config.debug_mode else None,
                    },
                    processing_status='processed'
                )
        except Exception as e:
            logger.error(f"Error tracking failed: {e}")
    
    def _update_user_journey(self, request, elapsed_time):
        """Update user journey for the current session"""
        try:
            session_id = request._analytics_data.get('session_id', '')
            if not session_id:
                return
            
            page_url = sanitize_url(request.build_absolute_uri())
            referrer = request.META.get('HTTP_REFERER', '')
            
            # Get or create journey
            journey, created = UserJourney.objects.get_or_create(
                session_id=session_id,
                defaults={
                    'user': request.user if request.user.is_authenticated else None,
                    'start_time': timezone.now(),
                    'entry_page': page_url,
                    'referrer_domain': self._extract_domain(referrer),
                    'device_type': self._detect_device_type(request._analytics_data.get('user_agent', ''))
                }
            )
            
            # Add page to journey path
            journey.add_page_visit(page_url)
            journey.end_time = timezone.now()
            journey.calculate_duration()
            
            # Update total events count  
            from django.db.models import F
            journey.total_events = F('total_events') + 1
            journey.save(update_fields=['end_time', 'total_events'])
            
        except Exception as e:
            logger.debug(f"Journey update error: {e}")
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return ''
    
    def _detect_device_type(self, user_agent):
        """Detect device type from user agent"""
        if not user_agent:
            return 'unknown'
        
        user_agent_lower = user_agent.lower()
        
        if any(mobile in user_agent_lower for mobile in ['mobile', 'android', 'iphone', 'ipod']):
            return 'mobile'
        elif 'ipad' in user_agent_lower or 'tablet' in user_agent_lower:
            return 'tablet'
        else:
            return 'desktop'
    
    def _log_error(self, component, exception, request=None):
        """Log errors to debug log for troubleshooting"""
        try:
            extra_data = {}
            if request:
                extra_data = {
                    'path': request.path,
                    'method': request.method,
                    'user': str(request.user) if request.user.is_authenticated else 'anonymous',
                }
            
            AnalyticsDebugLog.objects.create(
                level='ERROR',
                component=f'middleware.{component}',
                message=str(exception)[:500],
                extra_data=extra_data
            )
            
            # Also log to standard logger
            logger.error(f"Analytics middleware error in {component}: {exception}", exc_info=True)
            
        except Exception as log_error:
            # Last resort - just log to file
            logger.critical(f"Failed to log error: {log_error}")


class AnalyticsDebugMiddleware:
    """
    Debug middleware for analytics troubleshooting.
    Only active when debug mode is enabled.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        """Add debug headers and logging"""
        config = AnalyticsConfiguration.get_config()
        
        if not config.debug_mode:
            return self.get_response(request)
        
        # Add debug tracking
        request._analytics_debug = {
            'middleware_start': time.time(),
            'events_before': AnalyticsEvent.objects.count(),
        }
        
        response = self.get_response(request)
        
        # Add debug headers
        if hasattr(request, '_analytics_debug'):
            elapsed = time.time() - request._analytics_debug['middleware_start']
            events_after = AnalyticsEvent.objects.count()
            events_created = events_after - request._analytics_debug['events_before']
            
            response['X-Analytics-Time'] = f"{elapsed:.3f}s"
            response['X-Analytics-Events'] = str(events_created)
            response['X-Analytics-Session'] = request.session.get('analytics_session_id', 'none')
        
        return response