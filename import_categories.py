import os
import django
import csv
from django.utils.text import slugify

# Set up Django before importing any models
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "aps2026_site.settings.dev")
django.setup()

# Now it’s safe to import models
from home.models import NewsResearchItem, NewsItemCategory

csv_path = "import_files/APS-News-Categorized.csv"

updated = 0
not_found = []

with open(csv_path, newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        short_title = row["news_item_short_title"].strip()
        category_name = row["category"].strip()

        items = NewsResearchItem.objects.filter(news_item_short_title=short_title)
        if not items.exists():
            not_found.append(short_title)
            continue

        item = items.first()
        category_obj, _ = NewsItemCategory.objects.get_or_create(name=category_name)
        item.category = category_obj
        item.save()
        updated += 1

print(f"✅ Updated {updated} items.")
if not_found:
    print("⚠️ Could not find these items:")
    for title in not_found:
        print(" -", title)
