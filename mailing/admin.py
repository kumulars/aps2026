from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count
from .models import (
    MailingList, Subscriber, EmailTemplate, Campaign, 
    EmailLog, ClickTracking, AutomationRule
)


@admin.register(MailingList)
class MailingListAdmin(admin.ModelAdmin):
    list_display = ['name', 'list_type', 'subscriber_count', 'is_active', 'created_at']
    list_filter = ['list_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('Basic Info', {
            'fields': ('name', 'description', 'list_type', 'is_active')
        }),
        ('Filters (for dynamic lists)', {
            'fields': ('filter_country', 'filter_research_area', 'filter_member_type'),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    ]
    
    def subscriber_count(self, obj):
        count = obj.get_subscriber_count()
        if count > 0:
            url = reverse('admin:mailing_subscriber_changelist')
            return format_html('<a href="{}?lists__id__exact={}">{} subscribers</a>', url, obj.id, count)
        return '0 subscribers'
    subscriber_count.short_description = 'Subscribers'


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ['email', 'get_full_name', 'organization', 'country', 'is_member', 'is_researcher', 'is_active', 'subscribed_at']
    list_filter = ['is_active', 'is_member', 'is_researcher', 'confirmed', 'email_format', 'country', 'subscribed_at']
    search_fields = ['email', 'first_name', 'last_name', 'organization']
    filter_horizontal = ['lists']
    readonly_fields = ['subscribed_at', 'confirmation_token', 'confirmed_at', 'unsubscribed_at', 'last_email_at']
    
    fieldsets = [
        ('Contact Info', {
            'fields': ('email', 'first_name', 'last_name', 'organization', 'country')
        }),
        ('Subscription', {
            'fields': ('lists', 'is_active', 'subscribed_at', 'unsubscribed_at')
        }),
        ('Member Integration', {
            'fields': ('is_member', 'is_researcher', 'member_id', 'research_areas'),
            'classes': ['collapse']
        }),
        ('Preferences', {
            'fields': ('email_format', 'language'),
            'classes': ['collapse']
        }),
        ('Confirmation', {
            'fields': ('confirmed', 'confirmed_at', 'confirmation_token'),
            'classes': ['collapse']
        }),
        ('Statistics', {
            'fields': ('emails_received', 'emails_opened', 'emails_clicked', 'last_email_at'),
            'classes': ['collapse']
        }),
        ('GDPR/Compliance', {
            'fields': ('consent_given', 'consent_date', 'ip_address'),
            'classes': ['collapse']
        })
    ]
    
    actions = ['mark_as_member', 'mark_as_researcher', 'unsubscribe_users', 'export_to_csv']
    
    def mark_as_member(self, request, queryset):
        count = queryset.update(is_member=True)
        self.message_user(request, f'{count} subscribers marked as members.')
    mark_as_member.short_description = 'Mark selected as members'
    
    def mark_as_researcher(self, request, queryset):
        count = queryset.update(is_researcher=True)
        self.message_user(request, f'{count} subscribers marked as researchers.')
    mark_as_researcher.short_description = 'Mark selected as researchers'
    
    def unsubscribe_users(self, request, queryset):
        count = 0
        for subscriber in queryset:
            subscriber.unsubscribe()
            count += 1
        self.message_user(request, f'{count} subscribers unsubscribed.')
    unsubscribe_users.short_description = 'Unsubscribe selected users'


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'template_type', 'subject', 'is_active', 'created_at']
    list_filter = ['template_type', 'is_active', 'created_at']
    search_fields = ['name', 'subject']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('Basic Info', {
            'fields': ('name', 'template_type', 'subject', 'is_active')
        }),
        ('Content', {
            'fields': ('html_content', 'text_content')
        }),
        ('Template Variables', {
            'fields': ('available_variables',),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    ]


class EmailLogInline(admin.TabularInline):
    model = EmailLog
    extra = 0
    readonly_fields = ['subscriber', 'status', 'sent_at', 'opened_at', 'clicked_at', 'tracking_id']
    fields = ['subscriber', 'status', 'sent_at', 'opened_at', 'clicked_at', 'open_count', 'click_count']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'recipients_count', 'get_open_rate_display', 'get_click_rate_display', 'scheduled_for', 'sent_at']
    list_filter = ['status', 'created_at', 'sent_at', 'track_opens', 'track_clicks']
    search_fields = ['name', 'subject']
    filter_horizontal = ['mailing_lists']
    readonly_fields = ['recipients_count', 'sent_count', 'opened_count', 'clicked_count', 
                      'unsubscribed_count', 'bounced_count', 'created_at', 'updated_at']
    inlines = [EmailLogInline]
    
    fieldsets = [
        ('Campaign Info', {
            'fields': ('name', 'subject', 'status')
        }),
        ('Content', {
            'fields': ('template', 'html_content', 'text_content')
        }),
        ('Recipients', {
            'fields': ('mailing_lists', 'test_emails', 'recipients_count')
        }),
        ('Scheduling', {
            'fields': ('scheduled_for', 'sent_at')
        }),
        ('Settings', {
            'fields': ('from_name', 'from_email', 'reply_to'),
            'classes': ['collapse']
        }),
        ('Tracking', {
            'fields': ('track_opens', 'track_clicks', 'utm_source', 'utm_medium', 'utm_campaign'),
            'classes': ['collapse']
        }),
        ('Statistics', {
            'fields': ('sent_count', 'opened_count', 'clicked_count', 'unsubscribed_count', 'bounced_count'),
            'classes': ['collapse']
        }),
        ('Meta', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ['collapse']
        })
    ]
    
    def get_open_rate_display(self, obj):
        rate = obj.get_open_rate()
        if rate > 0:
            return f"{rate:.1f}%"
        return "-"
    get_open_rate_display.short_description = 'Open Rate'
    
    def get_click_rate_display(self, obj):
        rate = obj.get_click_rate()
        if rate > 0:
            return f"{rate:.1f}%"
        return "-"
    get_click_rate_display.short_description = 'Click Rate'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        obj.calculate_recipients()
        super().save_model(request, obj, form, change)
    
    actions = ['calculate_recipients', 'duplicate_campaign']
    
    def calculate_recipients(self, request, queryset):
        for campaign in queryset:
            campaign.calculate_recipients()
        self.message_user(request, f'Recipients calculated for {queryset.count()} campaigns.')
    calculate_recipients.short_description = 'Recalculate recipients'
    
    def duplicate_campaign(self, request, queryset):
        for campaign in queryset.filter(status='sent'):
            new_campaign = Campaign.objects.create(
                name=f"{campaign.name} (Copy)",
                subject=campaign.subject,
                template=campaign.template,
                html_content=campaign.html_content,
                text_content=campaign.text_content,
                from_name=campaign.from_name,
                from_email=campaign.from_email,
                reply_to=campaign.reply_to,
                created_by=request.user
            )
            new_campaign.mailing_lists.set(campaign.mailing_lists.all())
            new_campaign.calculate_recipients()
        self.message_user(request, f'{queryset.count()} campaigns duplicated.')
    duplicate_campaign.short_description = 'Duplicate selected campaigns'


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['campaign', 'subscriber', 'status', 'sent_at', 'opened_at', 'open_count', 'click_count']
    list_filter = ['status', 'sent_at', 'opened_at', 'clicked_at']
    search_fields = ['subscriber__email', 'campaign__name', 'tracking_id']
    readonly_fields = ['tracking_id', 'sent_at', 'opened_at', 'clicked_at', 'bounced_at', 'unsubscribed_at']
    
    fieldsets = [
        ('Basic Info', {
            'fields': ('campaign', 'subscriber', 'status', 'tracking_id')
        }),
        ('Timestamps', {
            'fields': ('sent_at', 'opened_at', 'clicked_at', 'bounced_at', 'unsubscribed_at')
        }),
        ('Statistics', {
            'fields': ('open_count', 'click_count')
        }),
        ('Error Info', {
            'fields': ('error_message',),
            'classes': ['collapse']
        })
    ]
    
    def has_add_permission(self, request):
        return False


@admin.register(ClickTracking)
class ClickTrackingAdmin(admin.ModelAdmin):
    list_display = ['email_log', 'url', 'clicked_at', 'ip_address']
    list_filter = ['clicked_at']
    search_fields = ['email_log__subscriber__email', 'url']
    readonly_fields = ['clicked_at']
    
    def has_add_permission(self, request):
        return False


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'trigger_type', 'template', 'delay_days', 'is_active', 'created_at']
    list_filter = ['trigger_type', 'is_active', 'created_at']
    search_fields = ['name']
    filter_horizontal = ['apply_to_lists']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = [
        ('Rule Info', {
            'fields': ('name', 'is_active')
        }),
        ('Trigger', {
            'fields': ('trigger_type', 'delay_days')
        }),
        ('Action', {
            'fields': ('template',)
        }),
        ('Conditions', {
            'fields': ('apply_to_lists',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        })
    ]