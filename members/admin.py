from django.contrib import admin
from django.db.models import Q
from django.shortcuts import render
from .models import Member, MembershipLevel


class HasNameFilter(admin.SimpleListFilter):
    title = 'has name'
    parameter_name = 'has_name'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Has both first and last name'),
            ('no', 'Missing first or last name'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.exclude(
                Q(first_name='') | Q(first_name__isnull=True),
                Q(last_name='') | Q(last_name__isnull=True)
            )
        elif self.value() == 'no':
            return queryset.filter(
                Q(first_name='') | Q(first_name__isnull=True) |
                Q(last_name='') | Q(last_name__isnull=True)
            )


@admin.register(MembershipLevel)
class MembershipLevelAdmin(admin.ModelAdmin):
    list_display = ['name', 'annual_dues', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'email', 'status', 'affiliation_type', 
        'data_source', 'directory_visible', 'is_verified', 'created_at'
    ]
    list_filter = [
        HasNameFilter, 'directory_visible', 'show_research_interests',
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
    
    # Pagination and ordering settings
    list_per_page = 75
    ordering = ['last_name', 'first_name']
    
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
        ('Privacy Settings', {
            'fields': ('directory_visible', 'show_research_interests')
        }),
        ('WordPress Data', {
            'fields': ('wp_user_id', 'wp_user_login')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'notes')
        }),
    )
    
    def get_queryset(self, request):
        """Default to showing only members with names"""
        qs = super().get_queryset(request)
        # Only apply default filter if no filter is explicitly set
        if not request.GET.get('has_name'):
            return qs.exclude(
                Q(first_name='') | Q(first_name__isnull=True),
                Q(last_name='') | Q(last_name__isnull=True)
            )
        return qs
    
    def full_name(self, obj):
        # Display in "Lastname, Firstname" format
        if obj.last_name and obj.first_name:
            return f"{obj.last_name}, {obj.first_name}"
        elif obj.last_name:
            return obj.last_name
        elif obj.first_name:
            return obj.first_name
        else:
            return f"[No Name] {obj.email}"
    full_name.short_description = 'Full Name'
    full_name.admin_order_field = 'last_name'  # Make the column sortable
    
    def directory_visible(self, obj):
        return obj.directory_visible
    directory_visible.boolean = True
    directory_visible.short_description = 'Visible in Directory'
    
    actions = ['hide_from_directory', 'show_in_directory', 'mark_as_verified', 'delete_selected_members']
    
    def hide_from_directory(self, request, queryset):
        updated = queryset.update(directory_visible=False)
        self.message_user(request, f'{updated} members hidden from directory.')
    hide_from_directory.short_description = 'Hide selected members from directory'
    
    def show_in_directory(self, request, queryset):
        # Only show members who have names
        members_with_names = queryset.exclude(
            Q(first_name='') | Q(first_name__isnull=True),
            Q(last_name='') | Q(last_name__isnull=True)
        )
        updated = members_with_names.update(directory_visible=True)
        skipped = queryset.count() - updated
        self.message_user(request, f'{updated} members shown in directory. {skipped} skipped (no names).')
    show_in_directory.short_description = 'Show selected members in directory'
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} members marked as verified.')
    mark_as_verified.short_description = 'Mark selected members as verified'
    
    def delete_selected_members(self, request, queryset):
        """Custom delete action with confirmation"""
        count = queryset.count()
        member_names = []
        for member in queryset[:5]:  # Show first 5 names
            name = member.full_name.strip() or f"[No Name] {member.email}"
            member_names.append(name)
        
        if count > 5:
            member_names.append(f"... and {count - 5} more")
            
        names_list = ", ".join(member_names)
        
        if request.POST.get('confirm_delete'):
            # Actually delete the members
            deleted_count = queryset.count()
            queryset.delete()
            self.message_user(
                request, 
                f'Successfully deleted {deleted_count} members: {names_list}',
                level='success'
            )
            return
        
        # Show confirmation page
        context = {
            'title': 'Confirm Member Deletion',
            'members': queryset,
            'count': count,
            'names_preview': names_list,
        }
        return render(request, 'admin/members/confirm_delete.html', context)
    
    delete_selected_members.short_description = 'Delete selected members (with confirmation)'
