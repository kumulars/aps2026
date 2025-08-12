from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import EmailValidator
from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
import uuid
import hashlib


class MailingList(models.Model):
    """Represents a mailing list/segment"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # List types
    LIST_TYPE_CHOICES = [
        ('all', 'All Subscribers'),
        ('members', 'APS Members'),
        ('researchers', 'Researchers'),
        ('symposium', 'Symposium Attendees'),
        ('custom', 'Custom List'),
    ]
    list_type = models.CharField(max_length=20, choices=LIST_TYPE_CHOICES, default='custom')
    
    # Segmentation criteria (for dynamic lists)
    filter_country = models.CharField(max_length=100, blank=True, help_text="Filter by country")
    filter_research_area = models.CharField(max_length=100, blank=True, help_text="Filter by research area")
    filter_member_type = models.CharField(max_length=50, blank=True, help_text="Filter by member type")
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.get_subscriber_count()} subscribers)"
    
    def get_subscriber_count(self):
        return self.subscribers.filter(is_active=True).count()
    
    def get_subscribers(self):
        """Get all active subscribers for this list"""
        if self.list_type == 'all':
            return Subscriber.objects.filter(is_active=True)
        elif self.list_type == 'members':
            return Subscriber.objects.filter(is_active=True, is_member=True)
        elif self.list_type == 'researchers':
            return Subscriber.objects.filter(is_active=True, is_researcher=True)
        else:
            # Apply filters for custom lists
            qs = self.subscribers.filter(is_active=True)
            if self.filter_country:
                qs = qs.filter(country=self.filter_country)
            if self.filter_research_area:
                qs = qs.filter(research_areas__icontains=self.filter_research_area)
            return qs


class Subscriber(models.Model):
    """Individual email subscriber"""
    email = models.EmailField(unique=True, validators=[EmailValidator()])
    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Subscription details
    lists = models.ManyToManyField(MailingList, related_name='subscribers', blank=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    
    # Member integration
    is_member = models.BooleanField(default=False)
    is_researcher = models.BooleanField(default=False)
    member_id = models.CharField(max_length=50, blank=True, help_text="APS member ID")
    research_areas = models.TextField(blank=True, help_text="Comma-separated research areas")
    
    # Preferences
    email_format = models.CharField(
        max_length=10,
        choices=[('html', 'HTML'), ('text', 'Plain Text')],
        default='html'
    )
    language = models.CharField(max_length=10, default='en')
    
    # Tracking
    confirmation_token = models.CharField(max_length=64, blank=True)
    confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    # Statistics
    emails_received = models.IntegerField(default=0)
    emails_opened = models.IntegerField(default=0)
    emails_clicked = models.IntegerField(default=0)
    last_email_at = models.DateTimeField(null=True, blank=True)
    
    # GDPR/Compliance
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    consent_given = models.BooleanField(default=False)
    consent_date = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-subscribed_at']
        
    def __str__(self):
        return f"{self.email} ({self.get_full_name()})"
    
    def get_full_name(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return "No name"
    
    def generate_confirmation_token(self):
        """Generate a unique confirmation token"""
        self.confirmation_token = hashlib.sha256(
            f"{self.email}{timezone.now()}{uuid.uuid4()}".encode()
        ).hexdigest()
        self.save()
        return self.confirmation_token
    
    def confirm_subscription(self):
        """Confirm the subscription"""
        self.confirmed = True
        self.confirmed_at = timezone.now()
        self.save()
    
    def unsubscribe(self):
        """Unsubscribe the user"""
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save()


@register_snippet
class EmailTemplate(ClusterableModel):
    """Reusable email templates"""
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    
    # Template content
    html_content = RichTextField(blank=True)
    text_content = models.TextField(blank=True, help_text="Plain text version")
    
    # Template variables
    available_variables = models.TextField(
        blank=True,
        help_text="Available template variables (e.g., {{first_name}}, {{organization}})",
        default="{{first_name}}, {{last_name}}, {{email}}, {{organization}}, {{unsubscribe_link}}"
    )
    
    # Categorization
    TEMPLATE_TYPE_CHOICES = [
        ('newsletter', 'Newsletter'),
        ('announcement', 'Announcement'),
        ('event', 'Event Invitation'),
        ('welcome', 'Welcome Email'),
        ('reminder', 'Reminder'),
        ('custom', 'Custom'),
    ]
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPE_CHOICES, default='custom')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    panels = [
        FieldPanel('name'),
        FieldPanel('template_type'),
        FieldPanel('subject'),
        FieldPanel('html_content'),
        FieldPanel('text_content'),
        FieldPanel('available_variables'),
        FieldPanel('is_active'),
    ]
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"


class Campaign(models.Model):
    """Email campaign"""
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    
    # Content
    template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    html_content = RichTextField(blank=True)
    text_content = models.TextField(blank=True)
    
    # Recipients
    mailing_lists = models.ManyToManyField(MailingList, blank=True)
    test_emails = models.TextField(
        blank=True,
        help_text="Comma-separated list of test email addresses"
    )
    
    # Scheduling
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    scheduled_for = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    recipients_count = models.IntegerField(default=0)
    sent_count = models.IntegerField(default=0)
    opened_count = models.IntegerField(default=0)
    clicked_count = models.IntegerField(default=0)
    unsubscribed_count = models.IntegerField(default=0)
    bounced_count = models.IntegerField(default=0)
    
    # Campaign settings
    from_name = models.CharField(max_length=100, default='American Peptide Society')
    from_email = models.EmailField(default='info@americanpeptidesociety.org')
    reply_to = models.EmailField(blank=True)
    
    # UTM tracking
    track_opens = models.BooleanField(default=True)
    track_clicks = models.BooleanField(default=True)
    utm_source = models.CharField(max_length=50, default='email')
    utm_medium = models.CharField(max_length=50, default='newsletter')
    utm_campaign = models.CharField(max_length=100, blank=True)
    
    # Meta
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='campaigns')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
    
    def get_open_rate(self):
        if self.sent_count > 0:
            return (self.opened_count / self.sent_count) * 100
        return 0
    
    def get_click_rate(self):
        if self.sent_count > 0:
            return (self.clicked_count / self.sent_count) * 100
        return 0
    
    def get_recipients(self):
        """Get all unique recipients from selected mailing lists"""
        subscribers = Subscriber.objects.none()
        for mailing_list in self.mailing_lists.all():
            subscribers = subscribers | mailing_list.get_subscribers()
        return subscribers.distinct()
    
    def calculate_recipients(self):
        """Calculate and store the number of recipients"""
        self.recipients_count = self.get_recipients().count()
        self.save()


class EmailLog(models.Model):
    """Log of individual emails sent"""
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='email_logs')
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name='email_logs')
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('bounced', 'Bounced'),
        ('unsubscribed', 'Unsubscribed'),
        ('failed', 'Failed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    open_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    
    # Error handling
    error_message = models.TextField(blank=True)
    
    # Unique tracking
    tracking_id = models.CharField(max_length=64, unique=True, blank=True)
    
    class Meta:
        ordering = ['-sent_at']
        unique_together = [['campaign', 'subscriber']]
        
    def __str__(self):
        return f"{self.campaign.name} -> {self.subscriber.email} ({self.get_status_display()})"
    
    def generate_tracking_id(self):
        """Generate a unique tracking ID for this email"""
        self.tracking_id = hashlib.sha256(
            f"{self.campaign.id}{self.subscriber.id}{uuid.uuid4()}".encode()
        ).hexdigest()
        self.save()
        return self.tracking_id


class ClickTracking(models.Model):
    """Track individual link clicks"""
    email_log = models.ForeignKey(EmailLog, on_delete=models.CASCADE, related_name='clicks')
    url = models.URLField()
    clicked_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-clicked_at']
        
    def __str__(self):
        return f"Click: {self.email_log.subscriber.email} -> {self.url}"


class AutomationRule(models.Model):
    """Automated email rules"""
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    
    # Trigger
    TRIGGER_CHOICES = [
        ('subscription', 'New Subscription'),
        ('member_join', 'New Member'),
        ('event_registration', 'Event Registration'),
        ('birthday', 'Birthday'),
        ('anniversary', 'Membership Anniversary'),
        ('custom', 'Custom Trigger'),
    ]
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    
    # Action
    template = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE)
    delay_days = models.IntegerField(default=0, help_text="Days to wait after trigger")
    
    # Conditions
    apply_to_lists = models.ManyToManyField(MailingList, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return f"{self.name} ({self.get_trigger_type_display()})"