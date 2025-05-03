from django.views.generic import TemplateView
from home.models import NewsResearchItem

class HomePageView(TemplateView):
    template_name = "home/home_page.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["news_items"] = NewsResearchItem.objects.order_by("-news_item_id")[:4]
        return context
