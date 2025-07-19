from django.contrib import admin
from .models import Member, MembershipLevel


@admin.register(MembershipLevel)
class MembershipLevelAdmin(admin.ModelAdmin):
    list_display = ['name', 'annual_dues', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'email', 'status', 'affiliation_type', 
        'data_source', 'is_verified', 'created_at'
    ]
    list_filter = [
        'status', 'affiliation_type', 'data_source', 'is_verified',
        'membership_level', 'legacy_match_type'
    ]
    search_fields = [
        'first_name', 'last_name', 'email', 'affiliation', 
        'legacy_id', 'wp_user_login'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'import_date', 
        'legacy_match_type', 'legacy_match_confidence'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('first_name', 'last_name', 'email', 'title', 'user')
        }),
        ('Contact Information', {
            'fields': ('phone', 'address_1', 'address_2', 'city', 'state', 'zip_code', 'country')
        }),
        ('Professional Information', {
            'fields': ('affiliation', 'affiliation_type', 'phd_year', 'research_interests')
        }),
        ('Membership Details', {
            'fields': ('membership_level', 'status', 'join_date', 'last_payment_date', 'membership_expires', 'is_verified')
        }),
        ('Data Tracking', {
            'fields': ('data_source', 'import_date', 'legacy_id', 'legacy_match_type', 'legacy_match_confidence')
        }),
        ('WordPress Data', {
            'fields': ('wp_user_id', 'wp_user_login')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'notes')
        }),
    )
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Name'
