from wagtail.snippets.views.snippets import SnippetViewSet
from wagtail.snippets.models import register_snippet
from home.models import Person

class PersonViewSet(SnippetViewSet):
    model = Person
    list_display = ["image_thumb", "first_name", "last_name", "category"]

register_snippet(Person, viewset=PersonViewSet)
