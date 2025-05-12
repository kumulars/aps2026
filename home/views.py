from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404
from home.models import NewsResearchItem
from django.utils.html import strip_tags

class HomePageView(TemplateView):
    template_name = "home/home_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["news_items"] = NewsResearchItem.objects.all().order_by("-id")[:5]
        return context


def news_item_detail_view(request, slug):
    item = get_object_or_404(NewsResearchItem, slug=slug)

    # Estimate content length safely
    full_text = item.news_item_full_text or ""
    full_text_length = len(strip_tags(full_text.strip()))

    if full_text_length < 500:
        sidebar_count = 2
    elif full_text_length < 1000:
        sidebar_count = 3
    elif full_text_length < 2000:
        sidebar_count = 4
    else:
        sidebar_count = 5

    recent = NewsResearchItem.objects.exclude(pk=item.pk).order_by("-id")[:sidebar_count]

    return render(request, "main/news_item_detail.html", {
        "page": item,
        "recent_news": recent,
    })
