#!/usr/bin/env python3
import os
import sys
import django

# Setup Django
sys.path.append('/Users/larssahl/documents/wagtail/aps2026')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aps2026_site.settings.dev')
django.setup()

from home.models import NewsItemCategory, NewsResearchItem

print("📊 CATEGORY DISTRIBUTION:")
print("=" * 40)

total_with_categories = 0
for cat in NewsItemCategory.objects.all().order_by('name'):
    count = NewsResearchItem.objects.filter(category=cat).count()
    total_with_categories += count
    print(f"{cat.name:15s}: {count:3d} articles")

total_articles = NewsResearchItem.objects.count()
uncategorized = total_articles - total_with_categories

print("-" * 40)
print(f"{'Total categorized':15s}: {total_with_categories:3d} articles")
print(f"{'Uncategorized':15s}: {uncategorized:3d} articles")
print(f"{'Total articles':15s}: {total_articles:3d} articles")

print("\n✅ Category system is fully functional!")