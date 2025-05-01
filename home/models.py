from django.db import models
from wagtail.snippets.models import register_snippet
from wagtail.admin.panels import FieldPanel
from django.utils import timezone
from wagtail.images.models import Image
from wagtail.models import Page

class HomePage(Page):
    pass

@register_snippet
class NewsResearchItem(models.Model):
    news_item_id = models.IntegerField(unique=True)
    news_item_entry_date = models.DateField(default=timezone.now)
    news_item_pi_first_name = models.CharField(max_length=100)
    news_item_pi_last_name = models.CharField(max_length=100)
    news_item_pi_title = models.CharField(max_length=200)
    news_item_pi_institution = models.CharField(max_length=200)
    news_item_pi_website = models.URLField(blank=True)
    news_item_short_title = models.CharField(max_length=100)
    news_item_blurb = models.TextField()
    news_item_full_text = models.TextField()
    news_item_image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    news_item_full_title = models.CharField(max_length=300)
    news_item_full_title = models.CharField(max_length=300)
    news_item_authors = models.TextField()
    news_item_citation = models.TextField()
    news_item_journal_url = models.URLField(blank=True)






    panels = [
        FieldPanel("news_item_entry_date"),
        FieldPanel("news_item_pi_first_name"),
        FieldPanel("news_item_pi_last_name"),
        FieldPanel("news_item_pi_title"),
        FieldPanel("news_item_pi_institution"),
        FieldPanel("news_item_pi_website"),
        FieldPanel("news_item_short_title"),
        FieldPanel("news_item_blurb"),
        FieldPanel("news_item_full_text"),
        FieldPanel("news_item_image"),
        FieldPanel("news_item_full_title"),
        FieldPanel("news_item_full_title"),
        FieldPanel("news_item_authors"),
        FieldPanel("news_item_citation"),
        FieldPanel("news_item_journal_url"),
        
    ]

    def __str__(self):
        return f"News Item {self.news_item_id}"
