import csv
from datetime import date
from django.utils.dateparse import parse_date
from home.models import NewsResearchItem
from wagtail.images.models import Image

CSV_PATH = "import_files/aps_news_import_cleaned.csv"

created_count = 0
skipped_count = 0
missing_images = []

with open(CSV_PATH, newline='', encoding="utf-8") as f:
    reader = csv.DictReader(f)

    for row in reader:
        # Fix BOM key if needed
        if "\ufeffnews_item_id" in row:
            row["news_item_id"] = row.pop("\ufeffnews_item_id")

        # Skip duplicates
        if NewsResearchItem.objects.filter(news_item_id=int(row["news_item_id"])).exists():
            skipped_count += 1
            continue

        # Find image
        image = Image.objects.filter(file__icontains=row["news_item_image_name"]).first()
        if not image:
            missing_images.append(row["news_item_image_name"])

        # Create item
        NewsResearchItem.objects.create(
            news_item_id=int(row["news_item_id"]),
            news_item_entry_date=parse_date(row["news_item_entry_date"]) or date.today(),
            news_item_pi_first_name=row["news_item_pi_first_name"].strip(),
            news_item_pi_last_name=row["news_item_pi_last_name"].strip(),
            news_item_pi_title=row["news_item_pi_title"].strip(),
            news_item_pi_institution=row["news_item_pi_institution"].strip(),
            news_item_pi_website=row["news_item_pi_website"].strip(),
            news_item_short_title=row["news_item_short_title"].strip(),
            news_item_blurb=row["news_item_blurb"].strip(),
            news_item_full_text=row["news_item_full_text"].strip(),
            news_item_full_title=row["news_item_full_title"].strip(),
            news_item_authors=row["news_item_authors"].strip(),
            news_item_citation=row["news_item_citation"].strip(),
            news_item_journal_url=row["news_item_journal_url"].strip(),
            news_item_image=image,
        )

        created_count += 1

print(f"\n✅ Imported {created_count} new items.")
print(f"⚠️ Skipped {skipped_count} duplicates.")
if missing_images:
    print(f"❌ {len(missing_images)} images not found:\n" + "\n".join(missing_images[:10]))
    if len(missing_images) > 10:
        print("...and more.")
