import csv
from datetime import datetime
from home.models import NewsResearchItem
from wagtail.images.models import Image

CSV_PATH = "import_files/APS-News-Export-2025-May-04-1306-CLEANED-BOM-STRICT.csv"

with open(CSV_PATH, newline='', encoding="utf-8") as f:
    reader = csv.DictReader(f)
    row = next(reader)

    if "\ufeffnews_item_id" in row:
        row["news_item_id"] = row.pop("\ufeffnews_item_id")

    if NewsResearchItem.objects.filter(news_item_id=int(row["news_item_id"])).exists():
        print("❌ Skipping duplicate")
    else:
        image = Image.objects.filter(file__icontains=row["news_item_image_name"]).first()
        item = NewsResearchItem.objects.create(
            news_item_id=int(row["news_item_id"]),
            news_item_entry_date=datetime.strptime(row["news_item_entry_date"], "%Y-%m-%d %H:%M:%S"),
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
        print("✅ News item created:", item)
