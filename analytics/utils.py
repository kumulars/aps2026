"""
Utility functions for analytics with error handling.
"""

import re
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import logging

logger = logging.getLogger('analytics')


def is_bot(user_agent, bot_patterns=None):
    """
    Detect if user agent is a bot.
    
    Args:
        user_agent: User agent string
        bot_patterns: List of patterns to match against
    
    Returns:
        Boolean indicating if user agent is a bot
    """
    try:
        if not user_agent:
            return False
        
        user_agent_lower = user_agent.lower()
        
        # Default bot patterns if none provided
        if bot_patterns is None:
            bot_patterns = [
                'bot', 'crawler', 'spider', 'scraper', 'googlebot',
                'bingbot', 'slackbot', 'twitterbot', 'facebookexternalhit',
                'linkedinbot', 'whatsapp', 'telegram', 'discord'
            ]
        
        # Check patterns
        for pattern in bot_patterns:
            if pattern.lower() in user_agent_lower:
                return True
        
        # Check for missing user agent indicators
        if len(user_agent) < 20:  # Suspiciously short
            return True
            
        # Check for common browser indicators (not bots)
        browser_indicators = ['mozilla', 'chrome', 'safari', 'firefox', 'edge', 'opera']
        has_browser = any(ind in user_agent_lower for ind in browser_indicators)
        
        # If no browser indicators but has programming language indicators
        if not has_browser:
            prog_indicators = ['python', 'java', 'ruby', 'perl', 'php', 'curl', 'wget']
            if any(ind in user_agent_lower for ind in prog_indicators):
                return True
        
        return False
        
    except Exception as e:
        logger.debug(f"Bot detection error: {e}")
        return False  # Default to not bot on error


def get_client_ip(request):
    """
    Get client IP address from request, handling proxies.
    
    Args:
        request: Django request object
    
    Returns:
        IP address string or None
    """
    try:
        # Check for proxy headers
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP if multiple are present
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            # Check other proxy headers
            ip = request.META.get('HTTP_X_REAL_IP')
            if not ip:
                ip = request.META.get('REMOTE_ADDR')
        
        # Validate IP format (basic check)
        if ip:
            # Remove port if present
            if ':' in ip and not ip.count(':') > 1:  # IPv4 with port
                ip = ip.split(':')[0]
            
            # Basic validation
            if len(ip) > 45:  # Max IPv6 length
                return None
                
        return ip
        
    except Exception as e:
        logger.debug(f"IP extraction error: {e}")
        return None


def sanitize_url(url, remove_params=None):
    """
    Sanitize URL for storage, removing sensitive parameters.
    
    Args:
        url: URL string to sanitize
        remove_params: List of parameter names to remove
    
    Returns:
        Sanitized URL string
    """
    try:
        if not url:
            return ''
        
        # Limit URL length
        if len(url) > 500:
            url = url[:500]
        
        # Parse URL
        parsed = urlparse(url)
        
        # Remove sensitive query parameters
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            
            # Default sensitive parameters to remove
            sensitive_params = remove_params or [
                'password', 'token', 'key', 'secret', 'api_key', 
                'auth', 'session', 'csrf', 'credit_card'
            ]
            
            # Remove sensitive parameters
            for param in list(params.keys()):
                param_lower = param.lower()
                if any(sensitive in param_lower for sensitive in sensitive_params):
                    params[param] = ['[REDACTED]']
            
            # Rebuild query string
            new_query = urlencode(params, doseq=True)
            
            # Rebuild URL
            url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                ''  # Remove fragment
            ))
        
        return url
        
    except Exception as e:
        logger.debug(f"URL sanitization error: {e}")
        return url[:500] if url else ''  # Return truncated original on error


def hash_ip(ip_address):
    """
    Hash IP address for privacy while maintaining uniqueness for analytics.
    
    Args:
        ip_address: IP address string
    
    Returns:
        Hashed IP string
    """
    try:
        if not ip_address:
            return None
        
        # Add salt for security (you should use a proper secret)
        salt = "analytics_salt_2024"  # TODO: Move to settings
        
        # Create hash
        hash_input = f"{salt}:{ip_address}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        
    except Exception as e:
        logger.debug(f"IP hashing error: {e}")
        return None


def get_page_category(path):
    """
    Categorize page based on URL path.
    
    Args:
        path: URL path string
    
    Returns:
        Category string
    """
    try:
        if not path:
            return 'other'
        
        path_lower = path.lower()
        
        # Define categories
        categories = {
            'news': ['/news/', '/blog/', '/article/'],
            'research': ['/research/', '/publication/', '/paper/'],
            'people': ['/people/', '/staff/', '/researcher/', '/peptide-links/'],
            'events': ['/event/', '/symposium/', '/conference/', '/meeting/'],
            'resources': ['/resource/', '/download/', '/document/', '/file/'],
            'about': ['/about/', '/mission/', '/history/'],
            'contact': ['/contact/', '/support/'],
            'member': ['/member/', '/account/', '/profile/'],
            'search': ['/search/', '?q=', '?search='],
        }
        
        # Check each category
        for category, patterns in categories.items():
            if any(pattern in path_lower for pattern in patterns):
                return category
        
        # Check if homepage
        if path == '/' or path == '/home/':
            return 'home'
        
        return 'other'
        
    except Exception as e:
        logger.debug(f"Page categorization error: {e}")
        return 'other'


def calculate_session_duration(session_start, session_end):
    """
    Calculate session duration in seconds.
    
    Args:
        session_start: Start datetime
        session_end: End datetime
    
    Returns:
        Duration in seconds
    """
    try:
        if not session_start or not session_end:
            return 0
        
        duration = (session_end - session_start).total_seconds()
        
        # Sanity check - cap at 24 hours
        if duration > 86400:
            return 86400
        
        if duration < 0:
            return 0
            
        return int(duration)
        
    except Exception as e:
        logger.debug(f"Duration calculation error: {e}")
        return 0


def format_file_size(size_bytes):
    """
    Format file size in bytes to human readable string.
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        Formatted string
    """
    try:
        if not size_bytes or size_bytes < 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.2f} {units[unit_index]}"
            
    except Exception as e:
        logger.debug(f"File size formatting error: {e}")
        return "Unknown"