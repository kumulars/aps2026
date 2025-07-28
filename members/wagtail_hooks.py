from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel, ObjectList, TabbedInterface
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet
from django.urls import reverse, path
from django.utils.html import format_html
from django.contrib.auth.decorators import permission_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse
import csv
from datetime import datetime
from .models import Member, MembershipLevel


# Register Member as a snippet for Wagtail admin
@register_snippet
class MemberAdmin(SnippetViewSet):
    model = Member
    menu_label = 'Members'
    menu_icon = 'user'
    menu_order = 200
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = ['full_name', 'email', 'status', 'affiliation', 'created_at']
    list_filter = ['status', 'affiliation_type', 'data_source', 'is_verified']
    search_fields = ['first_name', 'last_name', 'email', 'affiliation']
    ordering = ['last_name', 'first_name']
    
    panels = [
        TabbedInterface([
            ObjectList([
                FieldPanel('first_name'),
                FieldPanel('last_name'),
                FieldPanel('email'),
                FieldPanel('title'),
            ], heading='Basic Information'),
            
            ObjectList([
                FieldPanel('phone'),
                FieldPanel('address_1'),
                FieldPanel('address_2'),
                FieldPanel('city'),
                FieldPanel('state'),
                FieldPanel('zip_code'),
                FieldPanel('country'),
            ], heading='Contact Information'),
            
            ObjectList([
                FieldPanel('affiliation'),
                FieldPanel('affiliation_type'),
                FieldPanel('phd_year'),
                FieldPanel('research_interests'),
            ], heading='Professional Information'),
            
            ObjectList([
                FieldPanel('membership_level'),
                FieldPanel('status'),
                FieldPanel('join_date'),
                FieldPanel('last_payment_date'),
                FieldPanel('membership_expires'),
                FieldPanel('is_verified'),
            ], heading='Membership Details'),
            
            ObjectList([
                FieldPanel('data_source'),
                FieldPanel('legacy_id'),
                FieldPanel('legacy_match_type'),
                FieldPanel('wp_user_id'),
                FieldPanel('wp_user_login'),
                FieldPanel('notes'),
            ], heading='Data Tracking'),
        ])
    ]


# Register MembershipLevel as a snippet
@register_snippet
class MembershipLevelAdmin(SnippetViewSet):
    model = MembershipLevel
    menu_label = 'Membership Levels'
    menu_icon = 'group'
    menu_order = 201
    add_to_settings_menu = False
    list_display = ['name', 'annual_dues', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    
    panels = [
        FieldPanel('name'),
        FieldPanel('description'),
        FieldPanel('annual_dues'),
        FieldPanel('is_active'),
    ]


# Add membership dashboard to admin menu
@hooks.register('register_admin_menu_item')
def register_membership_dashboard():
    return MenuItem(
        'Membership Dashboard',
        reverse('wagtailadmin_membership_dashboard'),
        icon_name='group',
        order=150
    )


# Add membership statistics to admin menu
@hooks.register('register_admin_menu_item') 
def register_membership_stats():
    return MenuItem(
        'Member Statistics',
        reverse('wagtailadmin_membership_stats'),
        icon_name='doc-full',
        order=151
    )


# Add export members menu item
@hooks.register('register_admin_menu_item')
def register_export_members():
    return MenuItem(
        'Export Members',
        reverse('wagtailadmin_export_members'),
        icon_name='download',
        order=152
    )


# Register custom admin URLs
@hooks.register('register_admin_urls')
def register_membership_admin_urls():
    return [
        path('membership-dashboard/', membership_dashboard_view, name='wagtailadmin_membership_dashboard'),
        path('membership-stats/', membership_stats_view, name='wagtailadmin_membership_stats'),
        path('bulk-member-actions/', bulk_member_actions_view, name='wagtailadmin_bulk_member_actions'),
        path('export-members/', export_members_csv, name='wagtailadmin_export_members'),
    ]


@permission_required('members.view_member')
def membership_dashboard_view(request):
    """Membership overview dashboard"""
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    
    # Get membership statistics
    total_members = Member.objects.count()
    active_members = Member.objects.filter(status='active').count()
    pending_members = Member.objects.filter(status='pending').count()
    
    # Recent signups (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_signups = Member.objects.filter(created_at__gte=thirty_days_ago).count()
    
    # Data source breakdown
    data_sources = Member.objects.values('data_source').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Affiliation type breakdown
    affiliations = Member.objects.exclude(
        affiliation_type=''
    ).values('affiliation_type').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Recent members
    recent_members = Member.objects.order_by('-created_at')[:10]
    
    context = {
        'total_members': total_members,
        'active_members': active_members,
        'pending_members': pending_members,
        'recent_signups': recent_signups,
        'data_sources': data_sources,
        'affiliations': affiliations,
        'recent_members': recent_members,
    }
    
    return render(request, 'wagtailadmin/membership_dashboard.html', context)


@permission_required('members.view_member')
def membership_stats_view(request):
    """Detailed membership statistics"""
    from django.db.models import Count, Avg
    from collections import defaultdict
    
    # Status breakdown
    status_stats = Member.objects.values('status').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Geographic distribution
    country_stats = Member.objects.exclude(
        country=''
    ).values('country').annotate(
        count=Count('id')
    ).order_by('-count')[:20]
    
    # Membership levels
    level_stats = Member.objects.exclude(
        membership_level=None
    ).values('membership_level__name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # PhD year distribution
    phd_years = Member.objects.exclude(
        phd_year=None
    ).values('phd_year').annotate(
        count=Count('id')
    ).order_by('phd_year')
    
    # Group PhD years by decade for better visualization
    decade_stats = defaultdict(int)
    for item in phd_years:
        if item['phd_year']:
            decade = (item['phd_year'] // 10) * 10
            decade_stats[f"{decade}s"] += item['count']
    
    context = {
        'status_stats': status_stats,
        'country_stats': country_stats,
        'level_stats': level_stats,
        'decade_stats': dict(decade_stats),
        'total_members': Member.objects.count(),
    }
    
    return render(request, 'wagtailadmin/membership_stats.html', context)


@permission_required('members.change_member')
def bulk_member_actions_view(request):
    """Bulk member management actions"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'activate_all_pending':
            updated = Member.objects.filter(status='pending').update(status='active')
            messages.success(request, f'Activated {updated} pending members.')
            
        elif action == 'deactivate_legacy_only':
            updated = Member.objects.filter(data_source='legacy_only').update(status='inactive')
            messages.success(request, f'Deactivated {updated} legacy-only members.')
            
        elif action == 'verify_wordpress_members':
            updated = Member.objects.filter(data_source__in=['wordpress', 'merged']).update(is_verified=True)
            messages.success(request, f'Verified {updated} WordPress members.')
        
        return redirect('wagtailadmin_bulk_member_actions')
    
    # Get counts for preview
    pending_count = Member.objects.filter(status='pending').count()
    legacy_only_count = Member.objects.filter(data_source='legacy_only').count()
    unverified_wp_count = Member.objects.filter(
        data_source__in=['wordpress', 'merged'], 
        is_verified=False
    ).count()
    
    context = {
        'pending_count': pending_count,
        'legacy_only_count': legacy_only_count,
        'unverified_wp_count': unverified_wp_count,
    }
    
    return render(request, 'wagtailadmin/bulk_member_actions.html', context)


@permission_required('members.view_member')
def export_members_csv(request):
    """Export members to CSV file"""
    # Create the HttpResponse object with CSV header
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="aps_members_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'},
    )
    
    # Create CSV writer
    writer = csv.writer(response)
    
    # Get filter parameters from request
    status_filter = request.GET.get('status', '')
    affiliation_filter = request.GET.get('affiliation_type', '')
    data_source_filter = request.GET.get('data_source', '')
    
    # Start with all members
    members = Member.objects.all()
    
    # Apply filters if provided
    if status_filter:
        members = members.filter(status=status_filter)
    if affiliation_filter:
        members = members.filter(affiliation_type=affiliation_filter)
    if data_source_filter:
        members = members.filter(data_source=data_source_filter)
    
    # Order by last name, first name
    members = members.order_by('last_name', 'first_name')
    
    # Write CSV headers
    headers = [
        'ID', 'First Name', 'Last Name', 'Title', 'Email', 'Phone',
        'Affiliation', 'Affiliation Type', 'PhD Year',
        'Address 1', 'Address 2', 'City', 'State', 'ZIP', 'Country',
        'Status', 'Membership Level', 'Join Date', 'Last Payment', 'Expires',
        'Research Interests', 'Data Source', 'Verified', 'Created Date'
    ]
    writer.writerow(headers)
    
    # Write member data
    for member in members:
        row = [
            member.id,
            member.first_name,
            member.last_name,
            member.title or '',
            member.email,
            member.phone or '',
            member.affiliation or '',
            member.get_affiliation_type_display() if member.affiliation_type else '',
            member.phd_year or '',
            member.address_1 or '',
            member.address_2 or '',
            member.city or '',
            member.state or '',
            member.zip_code or '',
            member.country or '',
            member.get_status_display(),
            member.membership_level.name if member.membership_level else '',
            member.join_date.strftime('%Y-%m-%d') if member.join_date else '',
            member.last_payment_date.strftime('%Y-%m-%d') if member.last_payment_date else '',
            member.membership_expires.strftime('%Y-%m-%d') if member.membership_expires else '',
            member.research_interests or '',
            member.get_data_source_display(),
            'Yes' if member.is_verified else 'No',
            member.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ]
        writer.writerow(row)
    
    # Add summary information as comments at the end
    writer.writerow([])
    writer.writerow([f'# Total members exported: {members.count()}'])
    writer.writerow([f'# Export date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([f'# Exported by: {request.user.username}'])
    
    if status_filter:
        writer.writerow([f'# Status filter: {status_filter}'])
    if affiliation_filter:
        writer.writerow([f'# Affiliation filter: {affiliation_filter}'])
    if data_source_filter:
        writer.writerow([f'# Data source filter: {data_source_filter}'])
    
    return response