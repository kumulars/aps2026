from django.urls import reverse
from wagtail import hooks
from wagtail.admin.menu import MenuItem, Menu, SubmenuMenuItem
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from .models import MailingList, Subscriber, Campaign, EmailLog, AutomationRule


# Register models as Wagtail snippets for the main admin
class MailingListViewSet(SnippetViewSet):
    model = MailingList
    menu_label = 'Mailing Lists'
    icon = 'list-ul'
    menu_order = 100
    
    panels = [
        MultiFieldPanel([
            FieldPanel('name'),
            FieldPanel('description'),
            FieldPanel('list_type'),
            FieldPanel('is_active'),
        ], heading='Basic Information'),
        
        MultiFieldPanel([
            FieldPanel('filter_country'),
            FieldPanel('filter_research_area'),
            FieldPanel('filter_member_type'),
        ], heading='Filters (for dynamic lists)', classname='collapsed'),
    ]
    
    list_display = ['name', 'list_type', 'get_subscriber_count', 'is_active', 'created_at']
    list_filter = ['list_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['name']

    def get_subscriber_count(self, obj):
        return obj.get_subscriber_count()
    get_subscriber_count.short_description = 'Subscribers'


class SubscriberViewSet(SnippetViewSet):
    model = Subscriber
    menu_label = 'Subscribers'
    icon = 'user'
    menu_order = 200
    
    panels = [
        MultiFieldPanel([
            FieldPanel('email'),
            FieldPanel('first_name'),
            FieldPanel('last_name'),
            FieldPanel('organization'),
            FieldPanel('country'),
        ], heading='Contact Information'),
        
        MultiFieldPanel([
            FieldPanel('lists'),
            FieldPanel('is_active'),
            FieldPanel('email_format'),
            FieldPanel('language'),
        ], heading='Subscription Settings'),
        
        MultiFieldPanel([
            FieldPanel('is_member'),
            FieldPanel('is_researcher'),
            FieldPanel('member_id'),
            FieldPanel('research_areas'),
        ], heading='Member Integration', classname='collapsed'),
        
        MultiFieldPanel([
            FieldPanel('confirmed'),
            FieldPanel('consent_given'),
            FieldPanel('consent_date'),
        ], heading='Compliance', classname='collapsed'),
    ]
    
    list_display = ['email', 'get_full_name', 'organization', 'country', 'is_member', 'is_researcher', 'is_active', 'subscribed_at']
    list_filter = ['is_active', 'is_member', 'is_researcher', 'confirmed', 'email_format', 'country', 'subscribed_at']
    search_fields = ['email', 'first_name', 'last_name', 'organization']
    ordering = ['-subscribed_at']


class CampaignViewSet(SnippetViewSet):
    model = Campaign  
    menu_label = 'Email Campaigns'
    icon = 'mail'
    menu_order = 300
    
    panels = [
        MultiFieldPanel([
            FieldPanel('name'),
            FieldPanel('subject'),
            FieldPanel('status'),
        ], heading='Campaign Information'),
        
        MultiFieldPanel([
            FieldPanel('template'),
            FieldPanel('html_content'),
            FieldPanel('text_content'),
        ], heading='Content'),
        
        MultiFieldPanel([
            FieldPanel('mailing_lists'),
            FieldPanel('test_emails'),
        ], heading='Recipients'),
        
        MultiFieldPanel([
            FieldPanel('scheduled_for'),
            FieldPanel('from_name'),
            FieldPanel('from_email'),
            FieldPanel('reply_to'),
        ], heading='Settings', classname='collapsed'),
        
        MultiFieldPanel([
            FieldPanel('track_opens'),
            FieldPanel('track_clicks'),
            FieldPanel('utm_source'),
            FieldPanel('utm_medium'),
            FieldPanel('utm_campaign'),
        ], heading='Tracking', classname='collapsed'),
    ]
    
    list_display = ['name', 'status', 'recipients_count', 'get_open_rate_display', 'get_click_rate_display', 'scheduled_for', 'sent_at']
    list_filter = ['status', 'created_at', 'sent_at', 'track_opens', 'track_clicks']
    search_fields = ['name', 'subject']
    ordering = ['-created_at']

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


class EmailLogViewSet(SnippetViewSet):
    model = EmailLog
    menu_label = 'Email Logs'
    icon = 'doc-full-inverse'
    menu_order = 400
    
    panels = [
        MultiFieldPanel([
            FieldPanel('campaign'),
            FieldPanel('subscriber'),
            FieldPanel('status'),
        ], heading='Basic Information'),
        
        MultiFieldPanel([
            FieldPanel('sent_at'),
            FieldPanel('opened_at'),
            FieldPanel('clicked_at'),
            FieldPanel('open_count'),
            FieldPanel('click_count'),
        ], heading='Analytics', classname='collapsed'),
        
        MultiFieldPanel([
            FieldPanel('error_message'),
            FieldPanel('tracking_id'),
        ], heading='Technical Details', classname='collapsed'),
    ]
    
    list_display = ['campaign', 'subscriber', 'status', 'sent_at', 'opened_at', 'open_count', 'click_count']
    list_filter = ['status', 'sent_at', 'opened_at', 'clicked_at']
    search_fields = ['subscriber__email', 'campaign__name', 'tracking_id']
    ordering = ['-sent_at']


class AutomationRuleViewSet(SnippetViewSet):
    model = AutomationRule
    menu_label = 'Automation Rules'
    icon = 'cogs'
    menu_order = 500
    
    panels = [
        MultiFieldPanel([
            FieldPanel('name'),
            FieldPanel('is_active'),
            FieldPanel('trigger_type'),
            FieldPanel('delay_days'),
        ], heading='Rule Configuration'),
        
        MultiFieldPanel([
            FieldPanel('template'),
        ], heading='Action'),
        
        MultiFieldPanel([
            FieldPanel('apply_to_lists'),
        ], heading='Conditions'),
    ]
    
    list_display = ['name', 'trigger_type', 'template', 'delay_days', 'is_active', 'created_at']
    list_filter = ['trigger_type', 'is_active', 'created_at']
    search_fields = ['name']
    ordering = ['name']


# Register the viewsets with Wagtail
register_snippet(MailingList, viewset=MailingListViewSet)
register_snippet(Subscriber, viewset=SubscriberViewSet)
register_snippet(Campaign, viewset=CampaignViewSet)
register_snippet(EmailLog, viewset=EmailLogViewSet)
register_snippet(AutomationRule, viewset=AutomationRuleViewSet)


# Wagtail will automatically create menu items for registered snippets
# The mailing system models will appear in the "Snippets" menu


# Add custom actions to campaign admin
@hooks.register('register_admin_urls')
def register_mailing_admin_urls():
    from django.urls import path, include
    from .views import campaign_preview, send_test_email, send_campaign
    
    return [
        path('mailing/campaign/<int:campaign_id>/preview/', campaign_preview, name='mailing_campaign_preview'),
        path('mailing/campaign/<int:campaign_id>/send-test/', send_test_email, name='mailing_send_test_email'),
        path('mailing/campaign/<int:campaign_id>/send/', send_campaign, name='mailing_send_campaign'),
    ]


# Add custom CSS for better mailing admin appearance
@hooks.register('insert_global_admin_css')
def mailing_admin_css():
    return '''
    <style>
        /* Mailing system specific styles */
        .mailing-stats {
            display: flex;
            gap: 15px;
            margin: 10px 0;
        }
        
        .mailing-stat {
            background: #f8f9fa;
            padding: 10px 15px;
            border-radius: 4px;
            text-align: center;
            flex: 1;
        }
        
        .mailing-stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #2c5aa0;
        }
        
        .mailing-stat-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }
        
        /* Email template preview styling */
        .email-preview {
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 20px;
            margin: 10px 0;
            background: white;
        }
        
        /* Campaign action buttons */
        .campaign-actions {
            display: flex;
            gap: 10px;
            margin: 15px 0;
        }
        
        .campaign-actions .button {
            flex: 1;
            text-align: center;
        }
    </style>
    '''