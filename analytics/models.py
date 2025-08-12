from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator
import json
import logging

logger = logging.getLogger('analytics')


class AnalyticsEvent(models.Model):
    """
    Core analytics event model with error handling and data validation.
    Tracks all user interactions with fallback mechanisms.
    """
    
    EVENT_TYPES = [
        ('page_view', 'Page View'),
        ('search', 'Search'),
        ('click', 'Click'),
        ('form_submit', 'Form Submit'),
        ('download', 'Download'),
        ('error', 'Error'),
        ('api_call', 'API Call'),
        ('custom', 'Custom Event'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('retry', 'Retry'),
    ]
    
    # Core fields
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # User information (nullable for anonymous users)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    session_id = models.CharField(max_length=100, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Event details
    page_url = models.URLField(max_length=500, blank=True)
    referrer_url = models.URLField(max_length=500, blank=True)
    
    # Flexible data storage for event-specific information
    event_data = models.JSONField(default=dict, blank=True)
    
    # Error tracking
    processing_status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        db_index=True
    )
    error_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    
    # Performance metrics
    page_load_time = models.IntegerField(null=True, blank=True, help_text="Page load time in milliseconds")
    
    # Bot detection
    is_bot = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'event_type']),
            models.Index(fields=['session_id', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
        
    def __str__(self):
        return f"{self.event_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def mark_failed(self, error_message):
        """Mark event as failed with error tracking"""
        self.processing_status = 'failed'
        self.error_count += 1
        self.last_error = f"{timezone.now()}: {error_message}"
        self.save(update_fields=['processing_status', 'error_count', 'last_error'])
        
    def should_retry(self):
        """Determine if event should be retried"""
        return self.error_count < 3 and self.processing_status == 'failed'


class DailySummary(models.Model):
    """
    Aggregated daily statistics for performance and reporting.
    Pre-calculated to avoid expensive queries.
    """
    
    date = models.DateField(unique=True, db_index=True)
    
    # Traffic metrics
    total_page_views = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    unique_visitors = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    total_sessions = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Engagement metrics
    avg_session_duration = models.IntegerField(default=0, help_text="Average session duration in seconds")
    bounce_rate = models.FloatField(default=0.0, help_text="Percentage of single-page sessions")
    
    # Content metrics
    top_pages = models.JSONField(default=list, help_text="Top 10 pages with view counts")
    top_searches = models.JSONField(default=list, help_text="Top 20 search queries")
    
    # User metrics
    new_users = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    returning_users = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Error tracking
    error_count = models.IntegerField(default=0)
    error_details = models.JSONField(default=list)
    
    # Processing metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_complete = models.BooleanField(default=False)
    processing_errors = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Daily summaries"
        
    def __str__(self):
        return f"Summary for {self.date}"
    
    def add_error(self, error_type, error_message):
        """Add error to daily summary"""
        if not self.error_details:
            self.error_details = []
        self.error_details.append({
            'type': error_type,
            'message': error_message,
            'timestamp': timezone.now().isoformat()
        })
        self.error_count += 1
        self.save(update_fields=['error_details', 'error_count'])


class WeeklyReport(models.Model):
    """
    Weekly analytics reports with comparisons and insights.
    """
    
    week_start = models.DateField(db_index=True)
    week_end = models.DateField()
    
    # Report data
    report_data = models.JSONField(default=dict)
    
    # Email tracking
    sent_to = models.JSONField(default=list, help_text="List of email addresses")
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Status tracking
    is_generated = models.BooleanField(default=False)
    is_sent = models.BooleanField(default=False)
    generation_errors = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-week_start']
        unique_together = ['week_start', 'week_end']
        
    def __str__(self):
        return f"Report: {self.week_start} to {self.week_end}"


class AnalyticsDebugLog(models.Model):
    """
    Debug logging for analytics system troubleshooting.
    Separate from main events to avoid recursion.
    """
    
    LOG_LEVELS = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    level = models.CharField(max_length=10, choices=LOG_LEVELS)
    component = models.CharField(max_length=100, help_text="Component that generated the log")
    message = models.TextField()
    extra_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'level']),
        ]
        
    def __str__(self):
        return f"[{self.level}] {self.component}: {self.message[:50]}..."


class AnalyticsConfiguration(models.Model):
    """
    Singleton model for analytics configuration and feature flags.
    """
    
    # Feature flags
    enabled = models.BooleanField(default=True, help_text="Master on/off switch for analytics")
    track_page_views = models.BooleanField(default=True)
    track_searches = models.BooleanField(default=True)
    track_errors = models.BooleanField(default=True)
    track_downloads = models.BooleanField(default=True)
    
    # Performance settings
    sampling_rate = models.FloatField(
        default=1.0, 
        help_text="Sampling rate for high-traffic pages (0.0-1.0)"
    )
    max_events_per_minute = models.IntegerField(
        default=1000,
        help_text="Rate limiting for event tracking"
    )
    
    # Data retention (in days)
    raw_event_retention_days = models.IntegerField(default=30)
    daily_summary_retention_days = models.IntegerField(default=365)
    debug_log_retention_days = models.IntegerField(default=7)
    
    # Bot detection
    bot_user_agents = models.JSONField(
        default=list,
        help_text="List of user agent patterns to identify bots"
    )
    
    # Email settings
    report_recipients = models.JSONField(
        default=list,
        help_text="Email addresses for weekly reports"
    )
    send_weekly_reports = models.BooleanField(default=True)
    report_day = models.IntegerField(
        default=1,
        help_text="Day of week to send reports (1=Monday, 7=Sunday)"
    )
    
    # Debug settings
    debug_mode = models.BooleanField(default=False, help_text="Enable verbose logging")
    test_mode = models.BooleanField(default=False, help_text="Mark events as test data")
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Analytics Configuration"
        verbose_name_plural = "Analytics Configuration"
        
    def __str__(self):
        return f"Analytics Config (Updated: {self.updated_at})"
    
    @classmethod
    def get_config(cls):
        """Get or create the singleton configuration"""
        config, created = cls.objects.get_or_create(pk=1)
        if created:
            # Set default bot patterns
            config.bot_user_agents = [
                'bot', 'crawler', 'spider', 'scraper', 'Googlebot',
                'bingbot', 'Slackbot', 'TwitterBot', 'facebookexternalhit'
            ]
            config.save()
        return config
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists"""
        self.pk = 1
        super().save(*args, **kwargs)


# Import advanced models
from .models_advanced import (
    UserJourney, ABTest, ABTestParticipation, 
    CustomEvent, ConversionFunnel, UserSegment
)
