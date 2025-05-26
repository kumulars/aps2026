from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.utils.functional import cached_property
from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.images.models import Image
from wagtail.images.widgets import AdminImageChooser
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from modelcluster.models import ParentalKey, ClusterableModel


class HomePage(Page):
    def get_context(self, request):
        context = super().get_context(request)
        from .models import NewsResearchItem
        context["news_items"] = NewsResearchItem.objects.all().order_by("-id")[:5]
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

        def chunked(queryset, size):
            return [queryset[i:i + size] for i in range(0, len(queryset), size)]

        context["officer_rows"] = chunked(officers_ordered, 6)
        context["councilor_rows"] = chunked(list(councilors), 6)
        return context

    class Meta:
        verbose_name = "People Index Page"


@register_snippet
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
    news_item_full_title = models.CharField(max_length=300)
    news_item_authors = models.TextField()
    news_item_citation = models.TextField()
    news_item_journal_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    panels = [
        FieldPanel("news_item_entry_date"),
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
        ordering = ["-id"]
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
        InlinePanel("obituary", label="Obituary", max_num=1),
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
    person = ParentalKey("Person", on_delete=models.CASCADE, related_name="obituary", unique=True)
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
        items = NewsResearchItem.objects.all().order_by("-id")
        context["news_rows"] = chunked(list(items), 6)
        return context

class IntroPage(Page):
    body_text = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('body_text'),
    ]

    template = "home/intro_page.html"

