from django.views.generic import TemplateView
from django.shortcuts import render, get_object_or_404
from home.models import NewsResearchItem


class HomePageView(TemplateView):
    template_name = "home/home_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["news_items"] = NewsResearchItem.objects.all().order_by("-id")[:5]
        return context


def news_item_detail_view(request, slug):
    item = get_object_or_404(NewsResearchItem, slug=slug)
    recent = NewsResearchItem.objects.exclude(pk=item.pk).order_by('-news_item_entry_date')[:5]

    return render(request, "main/news_item_detail.html", {
        "page": item,
        "recent_news": recent,
    })
