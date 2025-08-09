from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404
from django.utils.html import strip_tags
from .models import NewsResearchItem, Obituary, Researcher
from .models import HighlightPanel, AwardRecipient, SymposiumImage
from members.models import Member, MembershipLevel
from django.http import HttpResponse, JsonResponse
from django.db import models
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from django.utils import timezone
from datetime import datetime
import hashlib
import secrets

class HomePageView(TemplateView):
    template_name = "home/home_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["news_items"] = NewsResearchItem.objects.all().order_by("-id")[:5]
        return context


def news_item_detail_view(request, slug):
    item = get_object_or_404(NewsResearchItem, slug=slug)

    # Estimate content length safely
    full_text = item.news_item_full_text or ""
    full_text_length = len(strip_tags(full_text.strip()))

    if full_text_length < 500:
        sidebar_count = 2
    elif full_text_length < 1000:
        sidebar_count = 3
    elif full_text_length < 2000:
        sidebar_count = 4
    else:
        sidebar_count = 5

    recent = NewsResearchItem.objects.exclude(pk=item.pk).order_by("-id")[:sidebar_count]

    return render(request, "main/news_item_detail.html", {
        "page": item,
        "recent_news": recent,
    })


def obituary_detail_view(request, slug):
    obit = get_object_or_404(Obituary, person__slug=slug)
    recent = Obituary.objects.exclude(pk=obit.pk).order_by("-obituary_id")[:5]

    return render(request, "main/obituary_detail.html", {
        "page": obit,
        "recent_obits": recent,
    })


def homepage_view(request):
    middle_column_items = HighlightPanel.objects.filter(column="middle")
    right_column_items = HighlightPanel.objects.filter(column="right")

    print("Middle column count:", middle_column_items.count())
    for item in middle_column_items:
        print(" -", item.title, "| Slug:", item.slug, "| Column:", item.column)

    return render(request, "home_page.html", {
        "news_items": [],  # just in case it's not provided elsewhere
        "middle_column_items": middle_column_items,
        "right_column_items": right_column_items,
    })

def highlight_detail(request, slug):
    item = get_object_or_404(HighlightPanel, slug=slug)

    tabs = []
    for i in range(1, 5):
        tabs.append({
            'title': getattr(item, f'tab{i}_title', None),
            'left': getattr(item, f'tab{i}_left_content', None),
            'images': [
                getattr(item, f'tab{i}_right_image', None),
                getattr(item, f'tab{i}_right_image_2', None),
                getattr(item, f'tab{i}_right_image_3', None),
                getattr(item, f'tab{i}_right_image_4', None),
            ]
        })

    return render(request, 'home/highlight_detail_tabs.html', {
        'object': item,
        'tabs': tabs,
    })


def award_recipient_detail_view(request, slug):
    """Display detailed information about an award recipient."""
    recipient = get_object_or_404(AwardRecipient, slug=slug, is_published=True)
    
    # Get other recipients of the same award
    related_recipients = AwardRecipient.objects.filter(
        award_type=recipient.award_type,
        is_published=True
    ).exclude(pk=recipient.pk).order_by('-year')[:5]
    
    return render(request, 'home/award_recipient_detail.html', {
        'recipient': recipient,
        'related_recipients': related_recipients,
    })


def researcher_suggestions_api(request):
    """API endpoint for researcher search suggestions"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    # Search for researchers matching the query
    researchers = Researcher.objects.filter(
        models.Q(first_name__icontains=query) |
        models.Q(last_name__icontains=query) |
        models.Q(institution__icontains=query),
        is_active=True
    )[:10]  # Limit to 10 suggestions
    
    suggestions = []
    for researcher in researchers:
        suggestions.append({
            'name': researcher.display_name,
            'institution': researcher.institution,
            'location': researcher.location_display
        })
    
    return JsonResponse({'suggestions': suggestions})


@csrf_exempt
def researcher_claim_profile_api(request):
    """API for researchers to claim their profiles"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        researcher_id = data.get('researcher_id')
        email = data.get('email', '').strip().lower()
        message = data.get('message', '')
        
        if not researcher_id or not email:
            return JsonResponse({'error': 'Researcher ID and email required'}, status=400)
            
        # Find researcher
        researcher = get_object_or_404(Researcher, id=researcher_id, is_active=True)
        
        # Generate verification token
        token = secrets.token_urlsafe(32)
        
        # Store claim request (you'd have a model for this)
        # For now, just send email to admin
        
        subject = f"Profile Claim Request - {researcher.display_name}"
        admin_message = f"""
A researcher has requested to claim their profile:

Researcher: {researcher.display_name}
Institution: {researcher.institution}
Email: {email}
Message: {message}

Please verify this claim and update the researcher's contact information.
        """
        
        # Send email to admins
        if hasattr(settings, 'ADMINS') and settings.ADMINS:
            admin_emails = [email_addr for name, email_addr in settings.ADMINS]
            send_mail(
                subject,
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                fail_silently=False,
            )
        
        # Send confirmation to researcher
        researcher_message = f"""
Thank you for claiming your profile in the APS Peptide Links directory.

We have received your request and will verify your information shortly. 
You will receive an email once your profile has been updated.

Profile: {researcher.display_name}
Institution: {researcher.institution}
        """
        
        send_mail(
            "Profile Claim Received - APS Peptide Links",
            researcher_message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        return JsonResponse({'success': True, 'message': 'Claim request submitted successfully'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def researcher_update_request_api(request):
    """API for researchers to request updates to their information"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Extract submitted data
        name = data.get('name', '').strip()
        institution = data.get('institution', '').strip()
        email = data.get('email', '').strip()
        website = data.get('website', '').strip()
        updates_requested = data.get('updates', '').strip()
        
        if not name or not email:
            return JsonResponse({'error': 'Name and email required'}, status=400)
        
        # Send update request to admin
        subject = f"Profile Update Request - {name}"
        admin_message = f"""
A researcher has requested updates to their profile:

Name: {name}
Institution: {institution}
Email: {email}
Website: {website}

Requested Updates:
{updates_requested}

Submitted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        if hasattr(settings, 'ADMINS') and settings.ADMINS:
            admin_emails = [email_addr for name, email_addr in settings.ADMINS]
            send_mail(
                subject,
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                fail_silently=False,
            )
        
        # Send confirmation to researcher
        researcher_message = f"""
Thank you for your profile update request.

We have received your information and will review and update your profile shortly.
You will receive an email confirmation once the changes have been made.

Name: {name}
Institution: {institution}
        """
        
        send_mail(
            "Update Request Received - APS Peptide Links",
            researcher_message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        return JsonResponse({'success': True, 'message': 'Update request submitted successfully'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def symposium_images_api(request, year):
    """API endpoint for loading symposium images by year with pagination."""
    try:
        limit_param = request.GET.get('limit', '30')
        
        if limit_param == 'all':
            # Load all images for the year
            images = SymposiumImage.objects.filter(
                year=year
            ).select_related(
                'thumbnail_image', 'full_image'
            ).order_by(
                'display_order', 'filename'
            )
            images_list = list(images)
            has_more = False
        else:
            # Paginated loading (legacy support)
            offset = int(request.GET.get('offset', 0))
            limit = int(limit_param)
            
            images = SymposiumImage.objects.filter(
                year=year
            ).select_related(
                'thumbnail_image', 'full_image'
            ).order_by(
                'display_order', 'filename'
            )[offset:offset + limit + 1]  # Get one extra to check if more exist
            
            images_list = list(images)
            has_more = len(images_list) > limit
            
            if has_more:
                images_list = images_list[:limit]  # Remove the extra one
        
        # Serialize the images
        image_data = []
        for image in images_list:
            data = {
                'filename': image.filename,
                'year': image.year,
                'event_date': image.event_date.isoformat() if image.event_date else None,
                'caption': image.caption,
                'thumbnail_url': image.thumbnail_url,
                'full_url': image.full_url,
            }
            image_data.append(data)
        
        return JsonResponse({
            'images': image_data,
            'has_more': has_more,
            'count': len(image_data)
        })
        
    except ValueError as e:
        return JsonResponse({'error': 'Invalid parameters'}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'Server error'}, status=500)


@csrf_exempt
def researcher_integrated_update_api(request):
    """Integrated API for researcher profile updates with membership signup"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        action = data.get('action')  # 'claim' or 'add_new'
        
        if action == 'claim':
            return handle_researcher_claim_with_membership(data)
        elif action == 'add_new':
            return handle_new_researcher_with_membership(data)
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def handle_researcher_claim_with_membership(data):
    """Handle claiming existing researcher profile with membership creation"""
    try:
        researcher_id = data.get('researcher_id')
        
        # Required membership fields
        email = data.get('email', '').strip().lower()
        phone = data.get('phone', '').strip()
        address_1 = data.get('address_1', '').strip()
        city = data.get('city', '').strip()
        state = data.get('state', '').strip()
        zip_code = data.get('zip_code', '').strip()
        country = data.get('country', '').strip()
        affiliation_type = data.get('affiliation_type', 'academic')
        research_interests = data.get('research_interests', '').strip()
        
        # Optional updates
        website_url = data.get('website_url', '').strip()
        orcid_id = data.get('orcid_id', '').strip()
        public_bio = data.get('public_bio', '').strip()
        
        if not researcher_id or not email:
            return JsonResponse({'error': 'Researcher ID and email are required'}, status=400)
            
        # Get researcher
        researcher = get_object_or_404(Researcher, id=researcher_id, is_active=True)
        
        # Check if member already exists
        existing_member = Member.objects.filter(email=email).first()
        
        if existing_member:
            # Link existing member to researcher
            if not researcher.member:
                researcher.member = existing_member
                researcher.save(update_fields=['member'])
            member = existing_member
        else:
            # Create new member
            member = Member.objects.create(
                first_name=researcher.first_name,
                last_name=researcher.last_name,
                email=email,
                title=researcher.title or '',
                phone=phone,
                address_1=address_1,
                city=city,
                state=state,
                zip_code=zip_code,
                country=country or researcher.country,
                affiliation=researcher.institution,
                affiliation_type=affiliation_type,
                research_interests=research_interests,
                status='active',
                data_source='peptidelinks_claim',
                join_date=timezone.now().date(),
                is_verified=True
            )
            
            # Link member to researcher
            researcher.member = member
        
        # Update researcher with new data
        if website_url:
            researcher.website_url = website_url
        if orcid_id:
            researcher.orcid_id = orcid_id
        if public_bio:
            researcher.public_bio = public_bio
            
        researcher.is_verified = True
        researcher.last_verified = timezone.now()
        researcher.save()
        
        # Send confirmation emails
        send_researcher_claim_confirmation(researcher, member)
        
        return JsonResponse({
            'success': True,
            'message': 'Profile claimed and membership created successfully!',
            'researcher_id': researcher.id,
            'member_id': member.id
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error processing claim: {str(e)}'}, status=500)


def handle_new_researcher_with_membership(data):
    """Handle adding new researcher with membership creation"""
    try:
        # Required fields
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        institution = data.get('institution', '').strip()
        email = data.get('email', '').strip().lower()
        
        # Address fields (required for membership)
        phone = data.get('phone', '').strip()
        address_1 = data.get('address_1', '').strip()
        city = data.get('city', '').strip()
        state = data.get('state', '').strip()
        zip_code = data.get('zip_code', '').strip()
        country = data.get('country', 'USA').strip()
        
        # Professional fields
        title = data.get('title', '').strip()
        department = data.get('department', '').strip()
        website_url = data.get('website_url', '').strip()
        orcid_id = data.get('orcid_id', '').strip()
        research_interests = data.get('research_interests', '').strip()
        affiliation_type = data.get('affiliation_type', 'academic')
        
        if not all([first_name, last_name, institution, email, address_1, city, state]):
            return JsonResponse({
                'error': 'Required fields: first name, last name, institution, email, address, city, state'
            }, status=400)
            
        # Check for existing member
        if Member.objects.filter(email=email).exists():
            return JsonResponse({'error': 'A member with this email already exists'}, status=400)
            
        # Create member first
        member = Member.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            title=title,
            phone=phone,
            address_1=address_1,
            city=city,
            state=state,
            zip_code=zip_code,
            country=country,
            affiliation=institution,
            affiliation_type=affiliation_type,
            research_interests=research_interests,
            status='active',
            data_source='peptidelinks_new',
            join_date=timezone.now().date(),
            is_verified=True
        )
        
        # Create researcher
        researcher = Researcher.objects.create(
            first_name=first_name,
            last_name=last_name,
            title=title,
            institution=institution,
            department=department,
            country=country,
            state_province=state,
            city=city,
            website_url=website_url,
            institutional_email=email,
            orcid_id=orcid_id,
            research_keywords=research_interests,
            is_active=True,
            is_verified=True,
            member=member,
            last_verified=timezone.now()
        )
        
        # Send welcome emails
        send_new_researcher_welcome(researcher, member)
        
        return JsonResponse({
            'success': True,
            'message': 'Welcome to PeptideLinks and APS membership!',
            'researcher_id': researcher.id,
            'member_id': member.id
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error creating profile: {str(e)}'}, status=500)


def send_researcher_claim_confirmation(researcher, member):
    """Send confirmation emails for claimed researcher profile"""
    try:
        # Email to researcher
        researcher_message = f"""
Thank you for claiming your profile in the APS Peptide Links directory!

Your profile has been successfully linked to your APS membership account.

Profile Details:
- Name: {researcher.display_name}
- Institution: {researcher.institution}
- Email: {member.email}

You can now:
- Update your research interests and contact information
- Access the member portal at /members/dashboard/
- Receive APS newsletters and announcements

Profile URL: https://americanpeptidesociety.org/explore/peptide-links/

Welcome to the APS community!
        """
        
        send_mail(
            "Profile Claimed - APS Peptide Links & Membership",
            researcher_message,
            settings.DEFAULT_FROM_EMAIL,
            [member.email],
            fail_silently=False,
        )
        
        # Email to admins
        if hasattr(settings, 'ADMINS') and settings.ADMINS:
            admin_message = f"""
Researcher Profile Claimed & Member Account Linked:

Researcher: {researcher.display_name}
Institution: {researcher.institution}
Email: {member.email}
Member ID: {member.id}
Researcher ID: {researcher.id}

The researcher now has access to both their PeptideLinks profile and member portal.
            """
            
            admin_emails = [email for name, email in settings.ADMINS]
            send_mail(
                f"Profile Claimed: {researcher.display_name}",
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                fail_silently=True,
            )
            
    except Exception as e:
        pass  # Don't fail the main process if email fails


def send_new_researcher_welcome(researcher, member):
    """Send welcome emails for new researcher + member"""
    try:
        # Email to new researcher/member
        welcome_message = f"""
Welcome to the APS Peptide Links directory and APS membership!

Your profile has been successfully created:

Profile Details:
- Name: {researcher.display_name}  
- Institution: {researcher.institution}
- Email: {member.email}
- Member ID: {member.id}

Your Benefits:
- Visibility in the global PeptideLinks directory
- Free APS membership with full benefits
- Access to member portal and resources
- Networking opportunities with peptide researchers worldwide

Next Steps:
1. Visit your profile: /explore/peptide-links/
2. Access member portal: /members/dashboard/
3. Update your research interests anytime

Thank you for joining the APS community!
        """
        
        send_mail(
            "Welcome to APS Peptide Links & Membership!",
            welcome_message,
            settings.DEFAULT_FROM_EMAIL,
            [member.email],
            fail_silently=False,
        )
        
        # Email to admins
        if hasattr(settings, 'ADMINS') and settings.ADMINS:
            admin_message = f"""
New Researcher Added to PeptideLinks + Membership:

Name: {researcher.display_name}
Institution: {researcher.institution}
Email: {member.email}
Country: {researcher.country}
Research Interests: {member.research_interests}

Both researcher profile and member account have been created and linked.
            """
            
            admin_emails = [email for name, email in settings.ADMINS]
            send_mail(
                f"New PeptideLinks Member: {researcher.display_name}",
                admin_message,
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                fail_silently=True,
            )
            
    except Exception as e:
        pass  # Don't fail the main process if email fails