from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.utils.functional import cached_property
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from wagtail.models import Page
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.images.models import Image
from wagtail.images.widgets import AdminImageChooser
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.contrib.forms.panels import FormSubmissionsPanel
from modelcluster.models import ParentalKey, ClusterableModel

import requests
from datetime import datetime, timedelta



class NewsItemCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "News Item Categories"






class HomePage(Page):
    def get_context(self, request):
        context = super().get_context(request)
        # Custom ordering: new items (import-*) first, then by entry date desc
        from django.db.models import Case, When, IntegerField
        
        context["news_items"] = NewsResearchItem.objects.annotate(
            custom_order=Case(
                When(news_item_id__startswith='import-', then=1),  # New items first
                default=2,
                output_field=IntegerField(),
            )
        ).order_by("custom_order", "-news_item_entry_date", "-id")[:15]
        
        # Add featured items for hero slider (top 5 most recent with images)
        context["hero_news_items"] = NewsResearchItem.objects.filter(
            news_item_image__isnull=False
        ).annotate(
            custom_order=Case(
                When(news_item_id__startswith='import-', then=1),  # New items first
                default=2,
                output_field=IntegerField(),
            )
        ).order_by("custom_order", "-news_item_entry_date", "-id")[:5]
        context["middle_column_items"] = HighlightPanel.objects.filter(
            column="middle", is_archived=False).order_by("sort_order")
        context["right_column_items"] = HighlightPanel.objects.filter(
            column="right", is_archived=False).order_by("sort_order")
        return context


class PeopleIndexPage(Page):
    template = "home/people_index_page.html"

    def get_context(self, request):
        context = super().get_context(request)

        officer_titles = [
            "President",
            "President Elect",
            "Secretary",
            "Treasurer",
            "Immediate Past President",
        ]

        officers_unsorted = Person.objects.filter(category__in=officer_titles)
        officers_ordered = []
        for title in officer_titles:
            matched = officers_unsorted.filter(category=title)
            officers_ordered.extend(matched)

        councilors = Person.objects.filter(category="Councilor").order_by("last_name")

        # ➕ Add staff (Lauren and Lars)
        staff = Person.objects.filter(category__in=["Society Manager", "Web Developer"]).order_by("last_name")

        def chunked(queryset, size):
            return [queryset[i:i + size] for i in range(0, len(queryset), size)]

        context["officer_rows"] = chunked(officers_ordered, 6)
        context["councilor_rows"] = chunked(list(councilors), 6)
        context["staff_rows"] = chunked(list(staff), 6)

        return context

    class Meta:
        verbose_name = "People Index Page"


class NewsResearchItem(models.Model):
    news_item_id = models.CharField(max_length=100, blank=True, null=True)
    news_item_entry_date = models.DateField(default=timezone.now)
    news_item_pi_first_name = models.CharField(max_length=100)
    news_item_pi_last_name = models.CharField(max_length=100)
    news_item_pi_title = models.CharField(max_length=200)
    news_item_pi_institution = models.CharField(max_length=200)
    news_item_pi_website = models.URLField(blank=True)
    news_item_short_title = models.CharField(max_length=100)
    slug = models.SlugField(blank=True, null=True)
    news_item_blurb = models.TextField()
    news_item_full_text = models.TextField(help_text="HTML content — rendered via `|safe` in template")
    news_item_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )
    news_item_image_caption = models.TextField(blank=True, help_text="Image caption in HTML format")
    news_item_full_title = models.CharField(max_length=300)
    news_item_authors = models.TextField()
    news_item_citation = models.TextField()
    news_item_journal_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    category = models.ForeignKey(
    "home.NewsItemCategory",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="news_items",
    )

    panels = [
        FieldPanel("news_item_entry_date"),
        FieldPanel("category"),
        FieldPanel("news_item_pi_first_name"),
        FieldPanel("news_item_pi_last_name"),
        FieldPanel("news_item_pi_title"),
        FieldPanel("news_item_pi_institution"),
        FieldPanel("news_item_pi_website"),
        FieldPanel("news_item_short_title"),
        FieldPanel("slug"),
        FieldPanel("news_item_blurb"),
        FieldPanel("news_item_full_text"),
        FieldPanel("news_item_image"),
        FieldPanel("news_item_image_caption"),
        FieldPanel("news_item_full_title"),
        FieldPanel("news_item_authors"),
        FieldPanel("news_item_citation"),
        FieldPanel("news_item_journal_url"),        
    ]

    def __str__(self):
        return self.news_item_short_title

    def save(self, *args, **kwargs):
        if not self.slug and self.news_item_short_title:
            self.slug = slugify(self.news_item_short_title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("news_item_detail", kwargs={"slug": self.slug})

    class Meta:
        ordering = ["-news_item_entry_date", "-id"]
        verbose_name = "News Research Item"
        verbose_name_plural = "News Research Items"


class Person(ClusterableModel):
    CATEGORY_CHOICES = [
        ("President", "President"),
        ("President Elect", "President Elect"),
        ("Immediate Past President", "Immediate Past President"),
        ("Past President", "Past President"),
        ("Secretary", "Secretary"),
        ("Treasurer", "Treasurer"),
        ("Councilor", "Councilor"),
        ("Society Manager", "Society Manager"),
        ("Web Developer", "Web Developer"),
        ("Honorary", "Honorary"),
        ("Obituary", "Obituary"),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    professional_title = models.CharField(max_length=255, blank=True)
    institution = models.CharField(max_length=255, blank=True)
    service_start_date = models.DateField(null=True, blank=True)
    service_end_date = models.DateField(null=True, blank=True)
    slug = models.SlugField(blank=True, unique=True)
    person_image = models.ForeignKey(
        Image, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    panels = [
        FieldPanel("category"),
        FieldPanel("first_name"),
        FieldPanel("last_name"),
        FieldPanel("professional_title"),
        FieldPanel("institution"),
        FieldPanel("service_start_date"),
        FieldPanel("service_end_date"),
        FieldPanel("person_image", widget=AdminImageChooser),
        InlinePanel("committee_roles", label="Committee Roles"),
    ]

    def image_thumb(self):
        if self.person_image:
            return format_html('<img src="{}" style="height: 50px;" />', self.person_image.file.url)
        return "(No image)"

    image_thumb.short_description = "Image"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.first_name} {self.last_name}")
            slug_candidate = base_slug
            num = 1
            while Person.objects.filter(slug=slug_candidate).exclude(pk=self.pk).exists():
                num += 1
                slug_candidate = f"{base_slug}-{num}"
            self.slug = slug_candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ["last_name", "first_name"]


class Committee(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class CommitteeMembership(models.Model):
    CHAIR = 'chair'
    MEMBER = 'member'
    ROLE_CHOICES = [
        (CHAIR, 'Chair'),
        (MEMBER, 'Member'),
    ]

    person = ParentalKey("Person", on_delete=models.CASCADE, related_name="committee_roles")
    committee = models.ForeignKey("Committee", on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    panels = [
        FieldPanel("committee"),
        FieldPanel("role"),
    ]

    class Meta:
        unique_together = ('person', 'committee', 'role')

    def __str__(self):
        return f"{self.person} - {self.role} of {self.committee}"


class PastPresidentsPage(Page):
    template = "home/past_presidents_page.html"

    def get_context(self, request):
        context = super().get_context(request)

        past_presidents = Person.objects.filter(
            category="Past President"
        ).order_by("-service_start_date")

        def chunked(queryset, size):
            return [queryset[i:i + size] for i in range(0, len(queryset), size)]

        context["past_president_rows"] = chunked(list(past_presidents), 6)
        return context


class Obituary(models.Model):
    person = models.OneToOneField("Person", on_delete=models.CASCADE, related_name="obituary")
    obituary_id = models.IntegerField()
    image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+"
    )
    blurb = models.TextField(
        help_text="Short HTML summary for obituary display only. Will be rendered as safe.",
        blank=True
    )
    full_text = models.TextField(
        help_text="Full obituary content. HTML allowed. For obituary use only.",
        blank=True
    )

    panels = [
        FieldPanel("obituary_id"),
        FieldPanel("image", widget=AdminImageChooser),
        FieldPanel("blurb"),
        FieldPanel("full_text"),
    ]

    class Meta:
        ordering = ["-obituary_id"]

    def __str__(self):
        return f"Obituary for {self.person.first_name} {self.person.last_name}"


class CommitteeIndexPage(Page):
    template = "home/committee_index_page.html"

    def get_context(self, request):
        from .models import NewsResearchItem
        context = super().get_context(request)
        context["committees"] = Committee.objects.prefetch_related("memberships__person").all().order_by("name")
        context["news_items"] = NewsResearchItem.objects.all().order_by("-id")[:6]
        return context


class ObituariesIndexPage(Page):
    template = "home/obituaries_index_page.html"

    def get_context(self, request):
        context = super().get_context(request)
        from home.models import Obituary
        context["obituaries"] = Obituary.objects.select_related("person").order_by("-obituary_id")
        return context

def chunked(queryset, size):
    return [queryset[i:i + size] for i in range(0, len(queryset), size)]

class NewsResearchIndexPage(Page):
    template = "home/news_research_index_page.html"

    def get_context(self, request):
        context = super().get_context(request)

        selected_category = request.GET.get("category")
        # Custom ordering: new items (import-*) first, then by entry date desc
        from django.db.models import Case, When, IntegerField
        
        if selected_category:
            items = NewsResearchItem.objects.filter(
                category__name=selected_category
            ).annotate(
                custom_order=Case(
                    When(news_item_id__startswith='import-', then=1),  # New items first
                    default=2,
                    output_field=IntegerField(),
                )
            ).order_by("custom_order", "-news_item_entry_date", "-id")
        else:
            items = NewsResearchItem.objects.all().annotate(
                custom_order=Case(
                    When(news_item_id__startswith='import-', then=1),  # New items first
                    default=2,
                    output_field=IntegerField(),
                )
            ).order_by("custom_order", "-news_item_entry_date", "-id")

        # Chunk items into rows of 6
        def chunked(qs, size):
            return [qs[i:i+size] for i in range(0, len(qs), size)]

        # Add category counts for enhanced UI
        categories_with_counts = []
        for category in NewsItemCategory.objects.all().order_by("name"):
            category.item_count = NewsResearchItem.objects.filter(category=category).count()
            categories_with_counts.append(category)

        context["news_rows"] = chunked(list(items), 6)
        context["categories"] = categories_with_counts
        context["selected_category"] = selected_category
        context["total_count"] = NewsResearchItem.objects.count()

        return context

class IntroPage(Page):
    body_text = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body_text'),
    ]

    template = "home/intro_page.html"

class HighlightPanelIndexPage(Page):
    template = "home/highlight_panel_index_page.html"

    def get_context(self, request):
        context = super().get_context(request)
        context["highlight_panels"] = HighlightPanel.objects.filter(is_archived=False).order_by("-sort_order")
        return context

    class Meta:
        verbose_name = "Highlight Panel Index Page"


@register_snippet
class HighlightPanel(ClusterableModel):
    COLUMN_CHOICES = [
        ("middle", "Middle Column"),
        ("right", "Right Column"),
    ]

    title = models.TextField(
    help_text="Paste HTML title. Will be rendered using the `|safe` filter.",
    blank=True)
    image = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_images'
    )

    html_body = models.TextField(
    help_text="Paste HTML. Will be rendered using the `|safe` filter.",
    blank=True)
    column = models.CharField(max_length=10, choices=COLUMN_CHOICES, default="middle")
    slug = models.SlugField(unique=True, help_text="Used to generate the detail page URL")
    month = models.CharField(max_length=20, blank=True, help_text="Month this feature was published")
    year = models.CharField(max_length=4, blank=True, help_text="Year this feature was published")
    is_lab_with_tabs = models.BooleanField(default=False)

    # Add these fields to the HighlightPanel model
    tab1_title = models.CharField(max_length=255, blank=True)
    tab1_left_content = models.TextField(
    help_text="Paste HTML. Will be rendered using the `|safe` filter.",
    blank=True)
    tab1_right_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab1_images'
    )

    tab1_right_image_2 = models.ForeignKey(
    'wagtailimages.Image',
    null=True, blank=True,
    on_delete=models.SET_NULL,
    related_name='highlight_tab1_images_2'
    )
    
    tab1_right_image_3 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab1_images_3'
    )
    
    tab1_right_image_4 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab1_images_4'
    )

    tab2_title = models.CharField(max_length=255, blank=True)
    tab2_left_content = models.TextField(
    help_text="Paste HTML. Will be rendered using the `|safe` filter.",
    blank=True)
    tab2_right_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab2_images'
    )

    tab2_right_image_2 = models.ForeignKey(
    'wagtailimages.Image',
    null=True, blank=True,
    on_delete=models.SET_NULL,
    related_name='highlight_tab2_images_2'
    )
    
    tab2_right_image_3 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab2_images_3'
    )
    
    tab2_right_image_4 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab2_images_4'
    )

    tab3_title = models.CharField(max_length=255, blank=True)
    tab3_left_content = models.TextField(
    help_text="Paste HTML. Will be rendered using the `|safe` filter.",
    blank=True)
    tab3_right_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab3_images'
    )

    tab3_right_image_2 = models.ForeignKey(
    'wagtailimages.Image',
    null=True, blank=True,
    on_delete=models.SET_NULL,
    related_name='highlight_tab3_images_2'
    )
    
    tab3_right_image_3 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab3_images_3'
    )
    
    tab3_right_image_4 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab3_images_4'
    )

    tab4_title = models.CharField(max_length=255, blank=True)
    tab4_left_content = models.TextField(
    help_text="Paste HTML. Will be rendered using the `|safe` filter.",
    blank=True)
    tab4_right_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab4_images'
    )

    tab4_right_image_2 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab4_images_2'
    )
    
    tab4_right_image_3 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab4_images_3'
    )
    
    tab4_right_image_4 = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='highlight_tab4_images_4'
    )

    is_archived = models.BooleanField(
        default=False,
        help_text="Uncheck to hide this panel from the homepage."
    )

    sort_order = models.IntegerField(
        default=0,
        help_text="Lower numbers appear first in the column."
    )

    panels = [
        FieldPanel("title"),
        FieldPanel("image", widget=AdminImageChooser),
        FieldPanel("html_body"),
        FieldPanel("column"),
        FieldPanel("slug"),
        FieldPanel("month"),
        FieldPanel("year"),
        FieldPanel("is_lab_with_tabs"),
        FieldPanel("tab1_title"),
        FieldPanel("tab1_left_content"),
        FieldPanel("tab1_right_image", widget=AdminImageChooser),
        FieldPanel("tab1_right_image_2", widget=AdminImageChooser),
        FieldPanel("tab1_right_image_3", widget=AdminImageChooser),
        FieldPanel("tab1_right_image_4", widget=AdminImageChooser),
        FieldPanel("tab2_title"),
        FieldPanel("tab2_left_content"),
        FieldPanel("tab2_right_image", widget=AdminImageChooser),
        FieldPanel("tab2_right_image_2", widget=AdminImageChooser),
        FieldPanel("tab2_right_image_3", widget=AdminImageChooser),
        FieldPanel("tab2_right_image_4", widget=AdminImageChooser),
        FieldPanel("tab3_title"),
        FieldPanel("tab3_left_content"),
        FieldPanel("tab3_right_image", widget=AdminImageChooser),
        FieldPanel("tab3_right_image_2", widget=AdminImageChooser),
        FieldPanel("tab3_right_image_3", widget=AdminImageChooser),
        FieldPanel("tab3_right_image_4", widget=AdminImageChooser),
        FieldPanel("tab4_title"),
        FieldPanel("tab4_left_content"),
        FieldPanel("tab4_right_image", widget=AdminImageChooser),
        FieldPanel("tab4_right_image_2", widget=AdminImageChooser),
        FieldPanel("tab4_right_image_3", widget=AdminImageChooser),
        FieldPanel("tab4_right_image_4", widget=AdminImageChooser),
        FieldPanel("is_archived"),
        FieldPanel("sort_order"),

    ]

    def get_absolute_url(self):
        return f"/highlight/{self.slug}/"

    def __str__(self):
        return self.title

@register_snippet
class SymposiumProceeding(models.Model):
    symposium_year = models.CharField(max_length=4)
    symposium_theme = models.CharField(max_length=255, blank=True)
    symposium_venue = models.CharField(max_length=255, blank=True)

    symposium_chair_1_name = models.CharField(max_length=255, blank=True)
    symposium_chair_1_institution = models.CharField(max_length=255, blank=True)
    symposium_chair_2_name = models.CharField(max_length=255, blank=True)
    symposium_chair_2_institution = models.CharField(max_length=255, blank=True)
    symposium_chair_3_name = models.CharField(max_length=255, blank=True)
    symposium_chair_3_institution = models.CharField(max_length=255, blank=True)

    cover_image = models.ForeignKey(
        'wagtailimages.Image',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    program_book = models.ForeignKey(
        'wagtaildocs.Document',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )

    panels = [
        FieldPanel("symposium_year"),
        FieldPanel("symposium_theme"),
        FieldPanel("symposium_venue"),

        FieldPanel("symposium_chair_1_name"),
        FieldPanel("symposium_chair_1_institution"),
        FieldPanel("symposium_chair_2_name"),
        FieldPanel("symposium_chair_2_institution"),
        FieldPanel("symposium_chair_3_name"),
        FieldPanel("symposium_chair_3_institution"),

        FieldPanel("cover_image", widget=AdminImageChooser),
        FieldPanel("program_book"),
    ]

    def __str__(self):
        return f"APS {self.symposium_year} Proceedings"

class ProceedingsIndexPage(Page):
    template = "home/proceedings_index_page.html"

    intro_text = RichTextField(
        blank=True,
        features=["bold", "italic", "link"]
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro_text"),
    ]

    @cached_property
    def proceedings(self):
        return SymposiumProceeding.objects.all().order_by("-symposium_year")
    
    def get_context(self, request):
        context = super().get_context(request)
        context["proceedings"] = self.proceedings
        return context

class ResearchArea(models.Model):
    """Research areas/specializations for researchers"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


@register_snippet
class Researcher(models.Model):
    """Core researcher model"""
    
    # Basic Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    title = models.CharField(max_length=200, blank=True, help_text="e.g., Professor, Associate Professor")
    
    # Institution Details
    institution = models.CharField(max_length=200)
    department = models.CharField(max_length=200, blank=True)
    
    # Geographic Information
    country = models.CharField(max_length=100, default="USA")
    state_province = models.CharField(max_length=100, blank=True, help_text="State (US) or Province (Canada)")
    city = models.CharField(max_length=100, blank=True)
    
    # Contact & Web Presence
    website_url = models.URLField(blank=True, help_text="Personal or lab website")
    institutional_email = models.EmailField(blank=True)
    orcid_id = models.CharField(max_length=50, blank=True, help_text="ORCID identifier (e.g., 0000-0000-0000-0000)")
    
    # PubMed Integration
    pubmed_search_term = models.CharField(max_length=200, blank=True, 
                                        help_text="Search term for PubMed (e.g., 'Smith J[Author]')")
    pubmed_url = models.URLField(blank=True)
    
    # Research Areas
    research_areas = models.ManyToManyField(ResearchArea, blank=True)
    research_keywords = models.TextField(blank=True, help_text="Comma-separated keywords")
    
    # Administrative Fields
    is_active = models.BooleanField(default=True, help_text="Display in public directory")
    is_verified = models.BooleanField(default=False, help_text="Verified by admin")
    verification_token = models.CharField(max_length=100, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_verified = models.DateTimeField(null=True, blank=True)
    last_link_check = models.DateTimeField(null=True, blank=True)
    
    # Status Tracking
    website_status = models.CharField(max_length=20, choices=[
        ('unknown', 'Unknown'),
        ('active', 'Active'),
        ('broken', 'Broken Link'),
        ('moved', 'Moved/Redirected'),
        ('inactive', 'Inactive')
    ], default='unknown')
    
    # Notes
    admin_notes = models.TextField(blank=True, help_text="Internal notes for administrators")
    public_bio = models.TextField(blank=True, help_text="Optional public biography")
    
    panels = [
        MultiFieldPanel([
            FieldPanel('first_name'),
            FieldPanel('last_name'),
            FieldPanel('title'),
        ], heading="Personal Information"),
        
        MultiFieldPanel([
            FieldPanel('institution'),
            FieldPanel('department'),
            FieldPanel('country'),
            FieldPanel('state_province'),
            FieldPanel('city'),
        ], heading="Institution"),
        
        MultiFieldPanel([
            FieldPanel('website_url'),
            FieldPanel('institutional_email'),
            FieldPanel('orcid_id'),
        ], heading="Contact & Web Presence"),
        
        MultiFieldPanel([
            FieldPanel('pubmed_search_term'),
            FieldPanel('pubmed_url'),
        ], heading="PubMed Information"),
        
        MultiFieldPanel([
            FieldPanel('research_areas'),
            FieldPanel('research_keywords'),
            FieldPanel('public_bio'),
        ], heading="Research Information"),
        
        MultiFieldPanel([
            FieldPanel('is_active'),
            FieldPanel('is_verified'),
            FieldPanel('website_status'),
            FieldPanel('admin_notes'),
        ], heading="Administrative"),
    ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.institution})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def display_name(self):
        if self.title:
            return f"{self.title} {self.full_name}"
        return self.full_name

    @property
    def location_display(self):
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state_province:
            parts.append(self.state_province)
        if self.country and self.country != "USA":
            parts.append(self.country)
        return ", ".join(parts) if parts else self.country

    def get_pubmed_url(self):
        """Generate PubMed URL from search term"""
        if self.pubmed_search_term:
            base_url = "https://www.ncbi.nlm.nih.gov/pubmed/"
            return f"{base_url}?term={self.pubmed_search_term}"
        return self.pubmed_url

    def check_website_status(self):
        """Check if website URL is accessible"""
        if not self.website_url:
            self.website_status = 'unknown'
            return False
            
        try:
            response = requests.head(self.website_url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                self.website_status = 'active'
                success = True
            elif 300 <= response.status_code < 400:
                self.website_status = 'moved'
                success = True
            else:
                self.website_status = 'broken'
                success = False
        except requests.RequestException:
            self.website_status = 'broken'
            success = False
        
        self.last_link_check = timezone.now()
        self.save(update_fields=['website_status', 'last_link_check'])
        return success

    def needs_verification(self):
        """Check if researcher info needs verification"""
        if not self.last_verified:
            return True
        
        # Needs verification if it's been more than 2 years
        cutoff = timezone.now() - timedelta(days=730)
        return self.last_verified < cutoff

    class Meta:
        ordering = ['last_name', 'first_name']
        unique_together = ['first_name', 'last_name', 'institution']


class PeptideLinksIndexPage(Page):
    """Main directory page"""
    
    intro_text = RichTextField(
        default="""
        <p>This site provides a directory of principal investigators in peptide science at academic institutions, 
        government laboratories, and companies who have research-oriented web pages. It serves the peptide science 
        community by connecting researchers across institutions and facilitating collaboration.</p>
        
        <p>The field of peptides is interdisciplinary, spanning chemistry, biochemistry, molecular biology, medicine, 
        pharmaceutical sciences, materials science, and engineering. While we cannot include every researcher who 
        uses peptides, we aim to provide a comprehensive directory of active peptide scientists.</p>
        """
    )
    
    submission_instructions = RichTextField(
        default="""
        <p>If you are a peptide scientist and principal investigator with a web page at your institution, 
        you may submit your information for inclusion in this directory. Please provide your name, 
        institution, research focus, and website URL.</p>
        """
    )

    content_panels = Page.content_panels + [
        FieldPanel('intro_text'),
        FieldPanel('submission_instructions'),
    ]

    def get_context(self, request):
        context = super().get_context(request)
        
        # Get search/filter parameters
        search_query = request.GET.get('search', '')
        country_filter = request.GET.get('country', '')
        state_filter = request.GET.get('state', '')
        research_area_filter = request.GET.get('research_area', '')
        
        # Base queryset
        researchers = Researcher.objects.filter(is_active=True)
        
        # Apply filters
        if search_query:
            researchers = researchers.filter(
                models.Q(first_name__icontains=search_query) |
                models.Q(last_name__icontains=search_query) |
                models.Q(institution__icontains=search_query) |
                models.Q(research_keywords__icontains=search_query)
            )
        
        if country_filter:
            researchers = researchers.filter(country=country_filter)
            
        if state_filter:
            researchers = researchers.filter(state_province=state_filter)
            
        if research_area_filter:
            researchers = researchers.filter(research_areas__slug=research_area_filter)
        
        # Group by location for display
        researchers_by_location = {}
        for researcher in researchers.select_related().prefetch_related('research_areas'):
            if researcher.country == 'USA':
                location_key = researcher.state_province or 'Unknown State'
            else:
                location_key = researcher.country
                
            if location_key not in researchers_by_location:
                researchers_by_location[location_key] = []
            researchers_by_location[location_key].append(researcher)
        
        # Custom sorting function for locations
        def sort_locations(location_item):
            """
            Custom sorting to match the original peptidelinks.net structure:
            1. US states first (alphabetically)
            2. Canada second  
            3. All other countries alphabetically
            """
            location_name, _ = location_item
            
            # Check if it's a US state (not in country list)
            # US states will be anything that's not a recognized country
            known_countries = {
                'Canada', 'Australia', 'Austria', 'Brazil', 'Chile', 'China', 'Cuba', 
                'Denmark', 'France', 'Germany', 'Greece', 'Iceland', 'India', 'Ireland', 
                'Israel', 'Italy', 'Japan', 'Netherlands', 'New Zealand', 'Pakistan', 
                'Portugal', 'Scotland', 'Singapore', 'South Korea', 'Spain', 'Sweden', 
                'Switzerland', 'U.K.', 'UK', 'United Kingdom', 'Vietnam'
                # Add more countries as needed
            }
            
            if location_name not in known_countries and location_name != 'Unknown State':
                # This is likely a US state
                return (0, location_name)  # Sort order 0 for US states
            elif location_name == 'Canada':
                return (1, location_name)  # Sort order 1 for Canada
            else:
                # All other countries
                return (2, location_name)  # Sort order 2 for other countries
        
        # Sort locations using custom function
        sorted_locations = sorted(researchers_by_location.items(), key=sort_locations)
        
        # Sort researchers within each location
        for location, researcher_list in sorted_locations:
            researcher_list.sort(key=lambda r: (r.last_name, r.first_name))
        
        # Get filter options
        countries = Researcher.objects.filter(is_active=True).values_list(
            'country', flat=True).distinct().order_by('country')
        states = Researcher.objects.filter(is_active=True, country='USA').values_list(
            'state_province', flat=True).distinct().order_by('state_province')
        research_areas = ResearchArea.objects.all()
        
        context.update({
            'researchers_by_location': sorted_locations,
            'search_query': search_query,
            'countries': countries,
            'states': states,
            'research_areas': research_areas,
            'selected_country': country_filter,
            'selected_state': state_filter,
            'selected_research_area': research_area_filter,
            'total_researchers': researchers.count(),
        })
        
        return context

    class Meta:
        verbose_name = "PeptideLinks Directory"


class ResearcherSubmissionFormField(AbstractFormField):
    """Form fields for researcher submission"""
    page = models.ForeignKey('ResearcherSubmissionPage', on_delete=models.CASCADE, related_name='form_fields')


class ResearcherSubmissionPage(AbstractEmailForm):
    """Page for researchers to submit their information"""
    
    intro = RichTextField(
        default="""
        <p>Use this form to submit your information for inclusion in the PeptideLinks directory. 
        All submissions are reviewed before being added to the public directory.</p>
        """
    )
    
    thank_you_text = RichTextField(
        default="""
        <p>Thank you for your submission! We will review your information and add you to the 
        directory once verified. You will receive a confirmation email when your listing is live.</p>
        """
    )

    content_panels = AbstractEmailForm.content_panels + [
        FieldPanel('intro'),
        InlinePanel('form_fields', label="Form Fields"),
        FieldPanel('thank_you_text'),
        MultiFieldPanel([
            FieldPanel('to_address'),
            FieldPanel('from_address'),
            FieldPanel('subject'),
        ], "Email"),
    ]

    def process_form_submission(self, form):
        """Process form submission and create pending researcher record"""
        submission = super().process_form_submission(form)
        
        # Extract form data
        form_data = {field.clean_name: field.value for field in submission.get_data()}
        
        # Create a pending researcher record
        researcher = Researcher(
            first_name=form_data.get('first_name', ''),
            last_name=form_data.get('last_name', ''),
            title=form_data.get('title', ''),
            institution=form_data.get('institution', ''),
            department=form_data.get('department', ''),
            country=form_data.get('country', 'USA'),
            state_province=form_data.get('state_province', ''),
            website_url=form_data.get('website_url', ''),
            institutional_email=form_data.get('email', ''),
            research_keywords=form_data.get('research_keywords', ''),
            public_bio=form_data.get('bio', ''),
            is_active=False,  # Pending admin approval
            is_verified=False,
        )
        researcher.save()
        
        return submission

    class Meta:
        verbose_name = "Researcher Submission Form"


class MembersOnlyPage(Page):
    """
    A page type that restricts access to active APS members only
    """
    intro = RichTextField(
        blank=True,
        help_text="Introduction text for members"
    )
    
    body = RichTextField(
        blank=True,
        features=['h2', 'h3', 'h4', 'bold', 'italic', 'link', 'ul', 'ol', 'blockquote', 'image', 'embed', 'document-link']
    )
    
    member_resources = RichTextField(
        blank=True,
        help_text="Special resources available only to members"
    )

    content_panels = Page.content_panels + [
        FieldPanel('intro'),
        FieldPanel('body'),
        FieldPanel('member_resources'),
    ]

    def serve(self, request):
        """Override serve method to check member status"""
        from django.shortcuts import redirect
        from django.contrib import messages
        from django.contrib.auth.decorators import login_required
        from django.utils.decorators import method_decorator
        from members.models import Member
        
        # Check if user is logged in
        if not request.user.is_authenticated:
            messages.info(request, 'Please log in to access member-only content.')
            return redirect(f'/accounts/login/?next={request.path}')
        
        # Check if user is an active member
        try:
            member = Member.objects.get(user=request.user)
            if member.status != 'active':
                messages.warning(
                    request,
                    'Active membership required to access this content. '
                    'Please renew your membership or contact us for assistance.'
                )
                return redirect('/members/dashboard/')
        except Member.DoesNotExist:
            messages.info(
                request,
                'Please complete your member profile to access this content.'
            )
            return redirect('/members/profile/')
        
        # If all checks pass, serve the page normally
        return super().serve(request)

    def get_context(self, request):
        context = super().get_context(request)
        
        # Add member-specific context
        if request.user.is_authenticated:
            try:
                member = Member.objects.get(user=request.user)
                context['member'] = member
            except Member.DoesNotExist:
                pass
        
        return context

    class Meta:
        verbose_name = "Members-Only Page"