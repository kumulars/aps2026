from django.utils.text import slugify
from django.utils.timezone import now
from home.models import NewsResearchItem

def run():
    seen = set()
    updated = 0

    for item in NewsResearchItem.objects.all():
        if not item.news_item_entry_date:
            item.news_item_entry_date = now().date()

        base_slug = slugify(item.news_item_short_title)
        slug = base_slug
        counter = 1
        while slug in seen or NewsResearchItem.objects.filter(slug=slug).exclude(pk=item.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        item.slug = slug
        seen.add(slug)
        item.save()
        updated += 1

    print(f"✅ Finished! Slugs generated for {updated} items.")

run()
