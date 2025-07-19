from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Member


def active_member_required(view_func):
    """
    Decorator that requires user to be an active member
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        try:
            member = Member.objects.get(user=request.user)
            if member.status == 'active':
                return view_func(request, *args, **kwargs)
            else:
                messages.warning(
                    request, 
                    'Active membership required to access this content. '
                    'Please renew your membership or contact us for assistance.'
                )
                return redirect('member_dashboard')
        except Member.DoesNotExist:
            messages.info(
                request,
                'Please complete your member profile to access this content.'
            )
            return redirect('member_profile')
    
    return _wrapped_view


def verified_member_required(view_func):
    """
    Decorator that requires user to be a verified member
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        try:
            member = Member.objects.get(user=request.user)
            if member.is_verified:
                return view_func(request, *args, **kwargs)
            else:
                messages.warning(
                    request,
                    'Account verification required to access this content. '
                    'Please check your email and verify your account.'
                )
                return redirect('member_dashboard')
        except Member.DoesNotExist:
            messages.info(
                request,
                'Please complete your member profile to access this content.'
            )
            return redirect('member_profile')
    
    return _wrapped_view