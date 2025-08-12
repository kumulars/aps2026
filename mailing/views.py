from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.template import Template, Context
from django.template.loader import render_to_string
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import logging
import hashlib
import urllib.parse
from .models import (
    Campaign, Subscriber, EmailLog, ClickTracking, 
    MailingList, EmailTemplate
)

logger = logging.getLogger(__name__)


@staff_member_required
def campaign_preview(request, campaign_id):
    """Preview a campaign before sending"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    # Use a sample subscriber for preview
    sample_subscriber = Subscriber.objects.filter(is_active=True).first()
    if not sample_subscriber:
        # Create a sample subscriber for preview
        sample_subscriber = Subscriber(
            email="preview@example.com",
            first_name="John",
            last_name="Doe",
            organization="Sample Organization"
        )
    
    # Render the email content
    html_content = render_email_content(campaign, sample_subscriber)
    
    return HttpResponse(html_content)


@staff_member_required
@require_POST
def send_test_email(request, campaign_id):
    """Send a test email to specified addresses"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    test_emails = request.POST.get('test_emails', campaign.test_emails)
    if not test_emails:
        messages.error(request, 'No test email addresses specified.')
        return redirect('admin:mailing_campaign_change', campaign_id)
    
    # Parse email addresses
    email_addresses = [email.strip() for email in test_emails.split(',')]
    sent_count = 0
    
    for email in email_addresses:
        if email:
            try:
                # Create a temporary subscriber for testing
                test_subscriber = Subscriber(
                    email=email,
                    first_name="Test",
                    last_name="User",
                    organization="Test Organization"
                )
                
                # Send the email
                if send_campaign_email(campaign, test_subscriber, is_test=True):
                    sent_count += 1
                    
            except Exception as e:
                logger.error(f"Failed to send test email to {email}: {e}")
    
    if sent_count > 0:
        messages.success(request, f'Test email sent to {sent_count} addresses.')
    else:
        messages.error(request, 'Failed to send test emails.')
    
    return redirect('admin:mailing_campaign_change', campaign_id)


@staff_member_required
@require_POST
def send_campaign(request, campaign_id):
    """Send a campaign to all recipients"""
    campaign = get_object_or_404(Campaign, id=campaign_id)
    
    if campaign.status not in ['draft', 'scheduled']:
        messages.error(request, 'Campaign cannot be sent in its current status.')
        return redirect('admin:mailing_campaign_change', campaign_id)
    
    # Update campaign status
    campaign.status = 'sending'
    campaign.sent_at = timezone.now()
    campaign.save()
    
    # Get all recipients
    recipients = campaign.get_recipients()
    campaign.recipients_count = recipients.count()
    campaign.save()
    
    # Send emails
    sent_count = 0
    failed_count = 0
    
    for subscriber in recipients:
        try:
            if send_campaign_email(campaign, subscriber):
                sent_count += 1
            else:
                failed_count += 1
        except Exception as e:
            logger.error(f"Failed to send email to {subscriber.email}: {e}")
            failed_count += 1
    
    # Update campaign statistics
    campaign.sent_count = sent_count
    campaign.status = 'sent'
    campaign.save()
    
    if sent_count > 0:
        messages.success(request, f'Campaign sent successfully! {sent_count} emails sent, {failed_count} failed.')
    else:
        messages.error(request, 'Campaign sending failed.')
    
    return redirect('admin:mailing_campaign_change', campaign_id)


def send_campaign_email(campaign, subscriber, is_test=False):
    """Send a single campaign email to a subscriber"""
    try:
        # Create or get email log
        if not is_test:
            email_log, created = EmailLog.objects.get_or_create(
                campaign=campaign,
                subscriber=subscriber,
                defaults={'status': 'pending'}
            )
            if not created and email_log.status == 'sent':
                # Don't send duplicate emails
                return True
        
        # Render email content
        html_content = render_email_content(campaign, subscriber)
        text_content = render_email_text_content(campaign, subscriber)
        
        # Add tracking pixels and links if not a test
        if not is_test:
            html_content = add_email_tracking(html_content, email_log)
        
        # Create email message
        subject = render_template_string(campaign.subject, subscriber)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=f"{campaign.from_name} <{campaign.from_email}>",
            to=[subscriber.email],
            reply_to=[campaign.reply_to] if campaign.reply_to else None
        )
        
        email.attach_alternative(html_content, "text/html")
        
        # Send the email
        email.send()
        
        # Update email log and subscriber stats
        if not is_test:
            email_log.status = 'sent'
            email_log.sent_at = timezone.now()
            email_log.generate_tracking_id()
            email_log.save()
            
            # Update subscriber stats
            subscriber.emails_received += 1
            subscriber.last_email_at = timezone.now()
            subscriber.save()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {subscriber.email}: {e}")
        if not is_test:
            email_log.status = 'failed'
            email_log.error_message = str(e)
            email_log.save()
        return False


def render_email_content(campaign, subscriber):
    """Render HTML email content with template variables"""
    content = campaign.html_content
    if campaign.template:
        content = campaign.template.html_content
    
    return render_template_string(content, subscriber)


def render_email_text_content(campaign, subscriber):
    """Render plain text email content"""
    content = campaign.text_content
    if campaign.template:
        content = campaign.template.text_content
    
    if not content:
        # Generate simple text version from HTML
        content = f"""
{render_template_string(campaign.subject, subscriber)}

This is a message from the American Peptide Society.

To view this email properly, please enable HTML in your email client.

To unsubscribe, visit: {{{{unsubscribe_link}}}}
"""
    
    return render_template_string(content, subscriber)


def render_template_string(template_string, subscriber):
    """Render template string with subscriber data"""
    template = Template(template_string)
    
    # Create unsubscribe link
    unsubscribe_token = hashlib.sha256(
        f"{subscriber.email}{subscriber.id}{settings.SECRET_KEY}".encode()
    ).hexdigest()
    unsubscribe_link = f"{settings.SITE_URL}/mailing/unsubscribe/{subscriber.id}/{unsubscribe_token}/"
    
    context = Context({
        'first_name': subscriber.first_name,
        'last_name': subscriber.last_name,
        'email': subscriber.email,
        'organization': subscriber.organization,
        'country': subscriber.country,
        'full_name': subscriber.get_full_name(),
        'unsubscribe_link': unsubscribe_link,
        'current_year': timezone.now().year,
    })
    
    return template.render(context)


def add_email_tracking(html_content, email_log):
    """Add tracking pixels and modify links for click tracking"""
    if not email_log or not email_log.campaign.track_opens:
        return html_content
    
    # Add tracking pixel for opens
    tracking_pixel = f'<img src="{settings.SITE_URL}/mailing/track/open/{email_log.tracking_id}/" width="1" height="1" style="display:none;" />'
    
    # Add before closing body tag, or at the end if no body tag
    if '</body>' in html_content:
        html_content = html_content.replace('</body>', f'{tracking_pixel}</body>')
    else:
        html_content += tracking_pixel
    
    # TODO: Add click tracking for links if needed
    # This would involve parsing HTML and replacing links with tracking URLs
    
    return html_content


def track_email_open(request, tracking_id):
    """Track email opens via pixel"""
    try:
        email_log = EmailLog.objects.get(tracking_id=tracking_id)
        
        # Update email log
        if email_log.status == 'sent':
            email_log.status = 'opened'
            email_log.opened_at = timezone.now()
        email_log.open_count += 1
        email_log.save()
        
        # Update campaign stats
        campaign = email_log.campaign
        if email_log.open_count == 1:  # First open
            campaign.opened_count += 1
            campaign.save()
        
        # Update subscriber stats
        subscriber = email_log.subscriber
        if email_log.open_count == 1:  # First open
            subscriber.emails_opened += 1
            subscriber.save()
        
    except EmailLog.DoesNotExist:
        pass
    
    # Return 1x1 transparent pixel
    pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x21\xF9\x04\x01\x00\x00\x00\x00\x2C\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x04\x01\x00\x3B'
    
    return HttpResponse(pixel_data, content_type='image/gif')


def track_email_click(request, tracking_id, encoded_url):
    """Track email clicks and redirect to original URL"""
    try:
        email_log = EmailLog.objects.get(tracking_id=tracking_id)
        original_url = urllib.parse.unquote(encoded_url)
        
        # Create click tracking record
        ClickTracking.objects.create(
            email_log=email_log,
            url=original_url,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Update email log
        if email_log.status in ['sent', 'opened']:
            email_log.status = 'clicked'
            email_log.clicked_at = timezone.now()
        email_log.click_count += 1
        email_log.save()
        
        # Update campaign stats
        campaign = email_log.campaign
        if email_log.click_count == 1:  # First click
            campaign.clicked_count += 1
            campaign.save()
        
        # Update subscriber stats
        subscriber = email_log.subscriber
        if email_log.click_count == 1:  # First click
            subscriber.emails_clicked += 1
            subscriber.save()
        
        return redirect(original_url)
        
    except EmailLog.DoesNotExist:
        return HttpResponse('Invalid tracking link', status=404)


def unsubscribe(request, subscriber_id, token):
    """Handle unsubscribe requests"""
    try:
        subscriber = get_object_or_404(Subscriber, id=subscriber_id)
        
        # Verify token
        expected_token = hashlib.sha256(
            f"{subscriber.email}{subscriber.id}{settings.SECRET_KEY}".encode()
        ).hexdigest()
        
        if token != expected_token:
            return HttpResponse('Invalid unsubscribe link', status=400)
        
        if request.method == 'POST':
            # Process unsubscribe
            subscriber.unsubscribe()
            
            return render(request, 'mailing/unsubscribed.html', {
                'subscriber': subscriber
            })
        
        # Show confirmation page
        return render(request, 'mailing/unsubscribe.html', {
            'subscriber': subscriber
        })
        
    except Subscriber.DoesNotExist:
        return HttpResponse('Subscriber not found', status=404)


def subscribe(request):
    """Handle subscription requests"""
    if request.method == 'POST':
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        organization = request.POST.get('organization', '')
        country = request.POST.get('country', '')
        
        if not email:
            return JsonResponse({'error': 'Email address is required'}, status=400)
        
        try:
            # Get or create subscriber
            subscriber, created = Subscriber.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'organization': organization,
                    'country': country,
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'consent_given': True,
                    'consent_date': timezone.now(),
                }
            )
            
            if not created and not subscriber.is_active:
                # Reactivate unsubscribed user
                subscriber.is_active = True
                subscriber.unsubscribed_at = None
                subscriber.save()
            
            # Add to default mailing lists
            default_lists = MailingList.objects.filter(
                list_type__in=['all', 'custom'],
                is_active=True
            )
            subscriber.lists.add(*default_lists)
            
            # Generate confirmation token and send confirmation email
            subscriber.generate_confirmation_token()
            # TODO: Send confirmation email
            
            return JsonResponse({
                'success': True,
                'message': 'Subscription successful! Please check your email to confirm.'
            })
            
        except Exception as e:
            logger.error(f"Subscription error: {e}")
            return JsonResponse({'error': 'Subscription failed'}, status=500)
    
    return render(request, 'mailing/subscribe.html')


def confirm_subscription(request, subscriber_id, token):
    """Confirm email subscription"""
    try:
        subscriber = get_object_or_404(Subscriber, id=subscriber_id)
        
        if subscriber.confirmation_token == token:
            subscriber.confirm_subscription()
            
            return render(request, 'mailing/confirmed.html', {
                'subscriber': subscriber
            })
        else:
            return HttpResponse('Invalid confirmation link', status=400)
            
    except Subscriber.DoesNotExist:
        return HttpResponse('Subscriber not found', status=404)