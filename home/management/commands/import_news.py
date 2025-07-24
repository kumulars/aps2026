import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from home.models import NewsResearchItem, NewsItemCategory
from wagtail.images.models import Image
from wagtail.images import get_image_model
import requests
from django.core.files.base import ContentFile


class Command(BaseCommand):
    help = 'Import news articles from WordPress export CSV'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file to import'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']
        
        if not os.path.exists(csv_file):
            self.stdout.write(
                self.style.ERROR(f'CSV file not found: {csv_file}')
            )
            return

        self.stdout.write(f"📂 Reading CSV file: {csv_file}")
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            imported_count = 0
            skipped_count = 0
            
            for row in reader:
                try:
                    if self.import_news_item(row, dry_run):
                        imported_count += 1
                    else:
                        skipped_count += 1
                        
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing row: {e}')
                    )
                    skipped_count += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'🔍 DRY RUN: Would import {imported_count} articles, skip {skipped_count}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Imported {imported_count} articles, skipped {skipped_count}'
                )
            )

    def import_news_item(self, row, dry_run=False):
        """Import a single news item from CSV row"""
        
        # Extract basic fields - using direct field names from clean CSV
        post_id = row.get('ID', '')
        
        # If no ID provided, generate one from the short title
        if not post_id:
            post_id = f"import-{slugify(row.get('news_item_short_title', ''))}"
        
        # Extract custom fields with correct column names
        pi_first_name = row.get('news_item_pi_first_name', '').strip()
        pi_last_name = row.get('news_item_pi_last_name', '').strip()
        pi_title = row.get('news_item_pi_title', '').strip()
        pi_institution = row.get('news_item_pi_institution', '').strip()
        pi_website = row.get('news_item_pi_website', '').strip()
        
        short_title = row.get('news_item_short_title', '').strip()
        blurb = row.get('news_item_blurb', '').strip() or row.get('ews_item_blurb', '').strip()
        full_text = row.get('news_item_full_text', '').strip()
        full_title = row.get('news_item_full_title', '').strip()
        
        # Skip if essential fields are missing
        if not short_title or not full_text:
            self.stdout.write(f"⚠️  Skipping row with missing title or content")
            return False
            
        authors = row.get('news_item_authors', '').strip()
        citation = row.get('news_item_citation', '').strip()
        journal_url = row.get('news_item_journal_url', '').strip()
        image_caption = row.get('news_item_image_caption', '').strip()
        
        # Check if already exists
        if NewsResearchItem.objects.filter(news_item_id=post_id).exists():
            self.stdout.write(f"⚠️  Skipping existing article: {short_title}")
            return False
        
        # Use today's date for entry date
        entry_date = timezone.now().date()

        # Generate slug
        slug = slugify(short_title)
        if not slug:
            slug = f"news-{post_id}"

        if dry_run:
            self.stdout.write(f"📰 Would import: {short_title} (PI: {pi_first_name} {pi_last_name})")
            return True

        # Create the news item
        news_item = NewsResearchItem.objects.create(
            news_item_id=post_id,
            news_item_entry_date=entry_date,
            news_item_pi_first_name=pi_first_name,
            news_item_pi_last_name=pi_last_name,
            news_item_pi_title=pi_title,
            news_item_pi_institution=pi_institution,
            news_item_pi_website=pi_website,
            news_item_short_title=short_title,
            slug=slug,
            news_item_blurb=blurb,
            news_item_full_text=full_text,
            news_item_image_caption=image_caption,
            news_item_full_title=full_title,
            news_item_authors=authors,
            news_item_citation=citation,
            news_item_journal_url=journal_url,
        )

        # Handle image if present
        image_url = row.get('wpcf-news-item-image', '').strip()
        if image_url and image_url.startswith('http'):
            self.download_and_attach_image(news_item, image_url)

        self.stdout.write(f"✅ Imported: {short_title}")
        return True

    def download_and_attach_image(self, news_item, image_url):
        """Download image from URL and attach to news item"""
        try:
            response = requests.get(image_url, timeout=30)
            if response.status_code == 200:
                # Extract filename from URL
                filename = image_url.split('/')[-1]
                if '?' in filename:
                    filename = filename.split('?')[0]
                if not filename.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    filename += '.jpg'

                # Create Wagtail image
                image_content = ContentFile(response.content)
                image = Image.objects.create(
                    title=f"News image for {news_item.news_item_short_title}",
                    file=image_content
                )
                
                # Attach to news item
                news_item.news_item_image = image
                news_item.save()
                
                self.stdout.write(f"  📷 Downloaded image: {filename}")
                
        except Exception as e:
            self.stdout.write(f"  ⚠️  Failed to download image {image_url}: {e}")