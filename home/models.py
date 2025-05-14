from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.admin.panels import FieldPanel
from wagtail.images.models import Image
from wagtail.images.widgets import AdminImageChooser
from django.utils.html import format_html
from django.db import models
from wagtail.models import Page
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.db.models import Q


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

        # Ordered officers (left to right in the top row)
        officer_titles = [
            "President",
            "President Elect",
            "Secretary",
            "Treasurer",
            "Immediate Past President",
        ]
        context["officers"] = [
            Person.objects.filter(category=title).first() for title in officer_titles
        ]

        # Councilors (could be paginated or further sorted later)
        context["councilors"] = Person.objects.filter(category="Councilor").order_by("last_name")

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
    slug = models.SlugField(unique=True, blank=True)
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


from django.db import models
from wagtail.models import Page
from wagtail.admin.panels import FieldPanel
from wagtail.images.models import Image
from wagtail.images.widgets import AdminImageChooser
from django.utils.html import format_html
from django.db.models import Q

class Person(models.Model):
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
    ]

    def image_thumb(self):
        if self.person_image:
            return format_html('<img src="{}" style="height: 50px;" />', self.person_image.file.url)
        return "(No image)"

    image_thumb.short_description = "Image"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ["last_name", "first_name"]


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
