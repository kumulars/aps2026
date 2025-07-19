from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import models
from .models import Member, MembershipLevel

User = get_user_model()


@login_required
def member_dashboard(request):
    """Member dashboard view"""
    try:
        member = Member.objects.get(user=request.user)
    except Member.DoesNotExist:
        # Create member profile if it doesn't exist
        from django.conf import settings
        default_status = 'active' if getattr(settings, 'APS_AUTO_ACTIVATE_MEMBERS', False) else 'pending'
        
        member = Member.objects.create(
            user=request.user,
            email=request.user.email,
            first_name=request.user.first_name or '',
            last_name=request.user.last_name or '',
            status=default_status
        )
        if default_status == 'active':
            messages.success(request, 'Welcome to the APS community! Your membership is active and ready to use.')
        else:
            messages.info(request, 'Welcome! Please complete your member profile.')
    
    context = {
        'member': member,
        'membership_levels': MembershipLevel.objects.filter(is_active=True)
    }
    return render(request, 'members/dashboard.html', context)


@login_required
def member_profile(request):
    """Member profile view and edit"""
    try:
        member = Member.objects.get(user=request.user)
    except Member.DoesNotExist:
        from django.conf import settings
        default_status = 'active' if getattr(settings, 'APS_AUTO_ACTIVATE_MEMBERS', False) else 'pending'
        
        member = Member.objects.create(
            user=request.user,
            email=request.user.email,
            first_name=request.user.first_name or '',
            last_name=request.user.last_name or '',
            status=default_status
        )
    
    if request.method == 'POST':
        # Update member profile
        member.first_name = request.POST.get('first_name', '')
        member.last_name = request.POST.get('last_name', '')
        member.title = request.POST.get('title', '')
        member.phone = request.POST.get('phone', '')
        member.address_1 = request.POST.get('address_1', '')
        member.address_2 = request.POST.get('address_2', '')
        member.city = request.POST.get('city', '')
        member.state = request.POST.get('state', '')
        member.zip_code = request.POST.get('zip_code', '')
        member.country = request.POST.get('country', '')
        member.affiliation = request.POST.get('affiliation', '')
        member.affiliation_type = request.POST.get('affiliation_type', '')
        member.phd_year = request.POST.get('phd_year') or None
        member.research_interests = request.POST.get('research_interests', '')
        
        member.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('member_profile')
    
    context = {
        'member': member,
        'affiliation_choices': Member.AFFILIATION_TYPE_CHOICES
    }
    return render(request, 'members/profile.html', context)


@login_required
def member_directory(request):
    """Public member directory view"""
    members = Member.objects.filter(status='active').order_by('last_name', 'first_name')
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        members = members.filter(
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query) |
            models.Q(affiliation__icontains=search_query) |
            models.Q(research_interests__icontains=search_query)
        )
    
    # Affiliation filtering
    affiliation_filter = request.GET.get('affiliation_type')
    if affiliation_filter:
        members = members.filter(affiliation_type=affiliation_filter)
    
    context = {
        'members': members,
        'search_query': search_query,
        'affiliation_filter': affiliation_filter,
        'affiliation_choices': Member.AFFILIATION_TYPE_CHOICES
    }
    return render(request, 'members/directory.html', context)


def member_detail(request, pk):
    """Individual member profile view"""
    member = get_object_or_404(Member, pk=pk, status='active')
    
    context = {
        'member': member
    }
    return render(request, 'members/detail.html', context)
