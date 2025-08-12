"""
Advanced analytics models for Stage 3 features:
- User journey mapping
- A/B testing
- Custom event tracking
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import AnalyticsEvent
import uuid
import json


class UserJourney(models.Model):
    """
    Track complete user journeys through the site.
    Maps session paths and conversion funnels.
    """
    
    session_id = models.CharField(max_length=100, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    
    # Journey metadata
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    
    # Journey characteristics
    entry_page = models.URLField(max_length=500)
    exit_page = models.URLField(max_length=500, blank=True)
    page_count = models.IntegerField(default=0)
    is_bounce = models.BooleanField(default=False)
    
    # Conversion tracking
    completed_goal = models.CharField(max_length=100, blank=True, help_text="Goal achieved during journey")
    conversion_value = models.FloatField(null=True, blank=True)
    
    # Journey path (JSON array of page URLs)
    page_path = models.JSONField(default=list)
    
    # Events during journey
    total_events = models.IntegerField(default=0)
    search_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    
    # Device and context
    device_type = models.CharField(max_length=20, blank=True)  # mobile, tablet, desktop
    referrer_domain = models.CharField(max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['session_id', '-start_time']),
            models.Index(fields=['entry_page', '-start_time']),
            models.Index(fields=['completed_goal', '-start_time']),
            models.Index(fields=['-start_time', 'page_count']),
        ]
    
    def __str__(self):
        return f"Journey {self.session_id[:8]} - {self.page_count} pages"
    
    def calculate_duration(self):
        """Calculate and update journey duration"""
        if self.end_time and self.start_time:
            self.duration_seconds = int((self.end_time - self.start_time).total_seconds())
            self.save(update_fields=['duration_seconds'])
    
    def add_page_visit(self, page_url):
        """Add page to journey path"""
        if not self.page_path:
            self.page_path = []
        
        # Don't duplicate consecutive pages
        if not self.page_path or self.page_path[-1] != page_url:
            self.page_path.append(page_url)
            self.page_count = len(self.page_path)
            
            # Update exit page
            self.exit_page = page_url
            
            # Check if bounce (only 1 page viewed)
            self.is_bounce = (self.page_count == 1)
            
            self.save(update_fields=['page_path', 'page_count', 'exit_page', 'is_bounce'])
    
    def mark_goal_completed(self, goal_name, value=None):
        """Mark conversion goal as completed"""
        self.completed_goal = goal_name
        self.conversion_value = value
        self.save(update_fields=['completed_goal', 'conversion_value'])


class ABTest(models.Model):
    """
    A/B testing configuration and management.
    """
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Test configuration
    is_active = models.BooleanField(default=False)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    
    # Traffic allocation
    traffic_allocation = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Percentage of traffic to include in test (0.0-1.0)"
    )
    
    # Test variants (JSON)
    variants = models.JSONField(default=dict, help_text="Variant configurations")
    
    # Goals and metrics
    primary_goal = models.CharField(max_length=100, blank=True)
    secondary_goals = models.JSONField(default=list)
    
    # Results tracking
    total_participants = models.IntegerField(default=0)
    conversions = models.JSONField(default=dict)  # variant -> conversion count
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"A/B Test: {self.name} ({'Active' if self.is_active else 'Inactive'})"
    
    def get_variant_for_session(self, session_id):
        """Determine which variant a session should see"""
        if not self.is_active or not self.variants:
            return None
        
        # Use session_id hash for consistent assignment
        import hashlib
        hash_value = int(hashlib.md5(f"{self.pk}:{session_id}".encode()).hexdigest()[:8], 16)
        
        # Check traffic allocation
        if (hash_value % 100) / 100.0 > self.traffic_allocation:
            return None  # Not in test
        
        # Assign variant
        variant_names = list(self.variants.keys())
        if not variant_names:
            return None
        
        variant_index = hash_value % len(variant_names)
        return variant_names[variant_index]
    
    def record_participation(self, session_id, variant):
        """Record a session's participation in the test"""
        participation, created = ABTestParticipation.objects.get_or_create(
            test=self,
            session_id=session_id,
            defaults={'variant': variant}
        )
        
        if created:
            self.total_participants += 1
            self.save(update_fields=['total_participants'])
        
        return participation
    
    def record_conversion(self, session_id, goal=None):
        """Record a conversion for this test"""
        try:
            participation = ABTestParticipation.objects.get(
                test=self,
                session_id=session_id
            )
            participation.mark_converted(goal or self.primary_goal)
            
            # Update test conversion counts
            if not self.conversions:
                self.conversions = {}
            
            variant = participation.variant
            if variant not in self.conversions:
                self.conversions[variant] = 0
            
            self.conversions[variant] += 1
            self.save(update_fields=['conversions'])
            
        except ABTestParticipation.DoesNotExist:
            pass  # User not in test


class ABTestParticipation(models.Model):
    """
    Individual user participation in an A/B test.
    """
    
    test = models.ForeignKey(ABTest, on_delete=models.CASCADE, related_name='participants')
    session_id = models.CharField(max_length=100)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    
    variant = models.CharField(max_length=50)
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    # Conversion tracking
    converted = models.BooleanField(default=False)
    conversion_goal = models.CharField(max_length=100, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    conversion_value = models.FloatField(null=True, blank=True)
    
    class Meta:
        unique_together = ['test', 'session_id']
        indexes = [
            models.Index(fields=['test', 'variant', 'converted']),
            models.Index(fields=['session_id', '-assigned_at']),
        ]
    
    def __str__(self):
        return f"{self.test.name} - {self.variant} ({self.session_id[:8]})"
    
    def mark_converted(self, goal=None, value=None):
        """Mark this participation as converted"""
        if not self.converted:
            self.converted = True
            self.conversion_goal = goal or self.test.primary_goal
            self.converted_at = timezone.now()
            self.conversion_value = value
            self.save(update_fields=['converted', 'conversion_goal', 'converted_at', 'conversion_value'])


class CustomEvent(models.Model):
    """
    Custom event tracking for specialized analytics.
    More flexible than standard AnalyticsEvent.
    """
    
    # Basic identification
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100, db_index=True)
    category = models.CharField(max_length=50, db_index=True)
    
    # Context
    session_id = models.CharField(max_length=100, blank=True, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Event details
    properties = models.JSONField(default=dict)
    value = models.FloatField(null=True, blank=True)
    
    # Context data
    page_url = models.URLField(max_length=500, blank=True)
    referrer_url = models.URLField(max_length=500, blank=True)
    
    # Device and technical
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Processing
    processed = models.BooleanField(default=False)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['category', 'name', '-timestamp']),
            models.Index(fields=['session_id', '-timestamp']),
            models.Index(fields=['-timestamp', 'processed']),
        ]
    
    def __str__(self):
        return f"{self.category}.{self.name} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"
    
    def mark_processed(self):
        """Mark event as processed"""
        self.processed = True
        self.processed_at = timezone.now()
        self.save(update_fields=['processed', 'processed_at'])


class ConversionFunnel(models.Model):
    """
    Define conversion funnels to track user progression.
    """
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Funnel steps (JSON array)
    steps = models.JSONField(default=list, help_text="Array of step definitions")
    
    # Configuration
    is_active = models.BooleanField(default=True)
    time_window_hours = models.IntegerField(
        default=24,
        help_text="Time window for funnel completion"
    )
    
    # Stats cache
    total_entries = models.IntegerField(default=0)
    total_completions = models.IntegerField(default=0)
    conversion_rate = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"Funnel: {self.name} ({self.conversion_rate:.1f}%)"
    
    def calculate_conversion_rate(self):
        """Calculate and update conversion rate"""
        if self.total_entries > 0:
            self.conversion_rate = (self.total_completions / self.total_entries) * 100
        else:
            self.conversion_rate = 0.0
        self.save(update_fields=['conversion_rate'])


class UserSegment(models.Model):
    """
    Define user segments for targeted analytics.
    """
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Segment criteria (JSON)
    criteria = models.JSONField(default=dict)
    
    # Segment stats
    user_count = models.IntegerField(default=0)
    last_calculated = models.DateTimeField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"Segment: {self.name} ({self.user_count} users)"
    
    def matches_session(self, session_id, user=None):
        """Check if a session matches this segment"""
        # Implementation would depend on criteria format
        # This is a placeholder for segment matching logic
        return False