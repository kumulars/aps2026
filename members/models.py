from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from wagtail.admin.panels import FieldPanel
from wagtail.models import Page
from wagtail.fields import RichTextField


class MembershipLevel(models.Model):
    """Membership levels and dues structure"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    annual_dues = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} (${self.annual_dues})"


class Member(models.Model):
    """Extended member profile linked to Django user"""
    DATA_SOURCE_CHOICES = [
        ('wordpress', 'WordPress Export'),
        ('legacy_only', 'Legacy Excel Only'),
        ('merged', 'Merged Data'),
        ('manual', 'Manual Entry'),
    ]
    
    MEMBERSHIP_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    AFFILIATION_TYPE_CHOICES = [
        ('academic', 'Academic'),
        ('industry', 'Industry'),
        ('government', 'Government'),
        ('nonprofit', 'Non-Profit'),
        ('student', 'Student'),
        ('retired', 'Retired'),
        ('other', 'Other'),
    ]
    
    # Basic information
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    title = models.CharField(max_length=50, blank=True)
    
    # Contact information
    phone = models.CharField(max_length=20, blank=True)
    address_1 = models.CharField(max_length=255, blank=True)
    address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Professional information
    affiliation = models.CharField(max_length=255, blank=True)
    affiliation_type = models.CharField(
        max_length=20, 
        choices=AFFILIATION_TYPE_CHOICES, 
        blank=True
    )
    phd_year = models.IntegerField(null=True, blank=True)
    research_interests = models.TextField(blank=True)
    
    # Membership details
    membership_level = models.ForeignKey(
        MembershipLevel, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    status = models.CharField(
        max_length=20, 
        choices=MEMBERSHIP_STATUS_CHOICES, 
        default='pending'
    )
    join_date = models.DateField(null=True, blank=True)
    last_payment_date = models.DateField(null=True, blank=True)
    membership_expires = models.DateField(null=True, blank=True)
    
    # Data tracking
    data_source = models.CharField(
        max_length=20, 
        choices=DATA_SOURCE_CHOICES, 
        default='manual'
    )
    import_date = models.DateTimeField(null=True, blank=True)
    
    # Legacy system data
    legacy_id = models.CharField(max_length=50, blank=True)
    legacy_match_type = models.CharField(max_length=50, blank=True)
    legacy_match_confidence = models.FloatField(null=True, blank=True)
    
    # WordPress data
    wp_user_id = models.IntegerField(null=True, blank=True)
    wp_user_login = models.CharField(max_length=100, blank=True)
    
    # Privacy settings
    directory_visible = models.BooleanField(
        default=True, 
        help_text="Show this member in the public directory"
    )
    show_research_interests = models.BooleanField(
        default=True,
        help_text="Display research interests in directory"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['status']),
            models.Index(fields=['data_source']),
            models.Index(fields=['legacy_id']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def formatted_name(self):
        """Return name in 'Lastname, Firstname' format for admin display"""
        if self.last_name and self.first_name:
            return f"{self.last_name}, {self.first_name}"
        elif self.last_name:
            return self.last_name
        elif self.first_name:
            return self.first_name
        else:
            return f"[No Name] {self.email}"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def researcher_profile(self):
        """Check if this member has a researcher profile in PeptideLinks"""
        # This would typically check the home.Person model for a matching profile
        from home.models import Person
        try:
            Person.objects.get(
                first_name__iexact=self.first_name,
                last_name__iexact=self.last_name
            )
            return True
        except Person.DoesNotExist:
            return False
        except Person.MultipleObjectsReturned:
            return True
    
    def get_absolute_url(self):
        return reverse('member_detail', kwargs={'pk': self.pk})


class MemberDirectoryPage(Page):
    """Wagtail page for the member directory"""
    intro = models.TextField(blank=True)
    
    content_panels = Page.content_panels + [
        FieldPanel('intro'),
    ]
    
    def get_context(self, request):
        context = super().get_context(request)
        
        # Get active members who want to be in directory
        members = Member.objects.filter(
            status='active',
            directory_visible=True
        ).order_by('last_name', 'first_name')
        
        # Add search functionality
        search_query = request.GET.get('search')
        if search_query:
            members = members.filter(
                models.Q(first_name__icontains=search_query) |
                models.Q(last_name__icontains=search_query) |
                models.Q(affiliation__icontains=search_query) |
                models.Q(research_interests__icontains=search_query)
            )
        
        # Add affiliation filtering
        affiliation_filter = request.GET.get('affiliation_type')
        if affiliation_filter:
            members = members.filter(affiliation_type=affiliation_filter)
        
        context['members'] = members
        context['search_query'] = search_query
        context['affiliation_filter'] = affiliation_filter
        context['affiliation_choices'] = Member.AFFILIATION_TYPE_CHOICES
        
        return context
