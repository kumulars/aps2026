from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.snippets.models import register_snippet
from home.models import Person, NewsResearchItem, NewsItemCategory
from home.models import SymposiumProceeding

# Custom admin view for Person
class PersonViewSet(SnippetViewSet):
    model = Person
    list_display = ["image_thumb", "first_name", "last_name", "category"]


# Custom admin view for NewsItemCategory
class NewsItemCategoryViewSet(SnippetViewSet):
    model = NewsItemCategory
    list_display = ["name"]
    search_fields = ["name"]


class NewsResearchItemViewSet(SnippetViewSet):
    model = NewsResearchItem
    ordering = ["-id"]  # Sort by ID descending (most recent at top)
    list_display = [
        "news_item_short_title",
        "news_item_pi_last_name",
        "news_item_pi_institution",
        "category",
        "news_item_entry_date",
    ]
    search_fields = [
        "news_item_short_title",
        "news_item_pi_last_name",
        "news_item_pi_institution",
    ]
    list_per_page = 40

class SymposiumProceedingViewSet(SnippetViewSet):
    model = SymposiumProceeding
    icon = "doc-full"
    add_to_admin_menu = True
    menu_label = "Symposium Proceedings"
    menu_order = 300

register_snippet(Person, viewset=PersonViewSet)
register_snippet(NewsItemCategory, viewset=NewsItemCategoryViewSet)
register_snippet(NewsResearchItem, viewset=NewsResearchItemViewSet)
