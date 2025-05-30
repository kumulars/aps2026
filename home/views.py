from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404
from django.utils.html import strip_tags
from .models import NewsResearchItem, Obituary
from .models import HighlightPanel
from django.http import HttpResponse

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


def obituary_detail_view(request, slug):
    obit = get_object_or_404(Obituary, person__slug=slug)
    recent = Obituary.objects.exclude(pk=obit.pk).order_by("-obituary_id")[:5]

    return render(request, "main/obituary_detail.html", {
        "page": obit,
        "recent_obits": recent,
    })


def homepage_view(request):
    middle_column_items = HighlightPanel.objects.filter(column="middle")
    right_column_items = HighlightPanel.objects.filter(column="right")

    print("Middle column count:", middle_column_items.count())
    for item in middle_column_items:
        print(" -", item.title, "| Slug:", item.slug, "| Column:", item.column)

    return render(request, "home_page.html", {
        "news_items": [],  # just in case it's not provided elsewhere
        "middle_column_items": middle_column_items,
        "right_column_items": right_column_items,
    })

def highlight_detail(request, slug):
    item = get_object_or_404(HighlightPanel, slug=slug)

    tabs = []
    for i in range(1, 5):
        tabs.append({
            'title': getattr(item, f'tab{i}_title', None),
            'left': getattr(item, f'tab{i}_left_content', None),
            'images': [
                getattr(item, f'tab{i}_right_image', None),
                getattr(item, f'tab{i}_right_image_2', None),
                getattr(item, f'tab{i}_right_image_3', None),
                getattr(item, f'tab{i}_right_image_4', None),
            ]
        })

    return render(request, 'home/highlight_detail_tabs.html', {
        'object': item,
        'tabs': tabs,
    })
