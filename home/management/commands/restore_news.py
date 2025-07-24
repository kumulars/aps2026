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
    help = 'Restore news articles from archived CSV while preserving existing items'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-file',
            type=str,
            default='import_files/archive/APS-News-Categorized.csv',
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

        # Get list of existing IDs to preserve
        existing_ids = set(NewsResearchItem.objects.values_list('news_item_id', flat=True))
        self.stdout.write(f"📊 Preserving {len(existing_ids)} existing items")
        
        self.stdout.write(f"📂 Reading CSV file: {csv_file}")
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            imported_count = 0
            skipped_count = 0
            preserved_count = 0
            
            for row in reader:
                try:
                    # Check if this would conflict with existing items
                    post_id = row.get('ID', '')
                    if not post_id:
                        post_id = f"import-{slugify(row.get('news_item_short_title', ''))}"
                    
                    if post_id in existing_ids:
                        preserved_count += 1
                        continue
                    
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
                    f'🔍 DRY RUN: Would restore {imported_count} articles, preserve {preserved_count}, skip {skipped_count}'
                )
            )
        else:
            final_count = NewsResearchItem.objects.count()
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Restored {imported_count} articles, preserved {preserved_count}, skipped {skipped_count}'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(f'📈 Total articles now: {final_count}')
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
            return False
            
        authors = row.get('news_item_authors', '').strip()
        citation = row.get('news_item_citation', '').strip()
        journal_url = row.get('news_item_journal_url', '').strip()
        image_caption = row.get('news_item_image_caption', '').strip()
        
        # Check if already exists
        if NewsResearchItem.objects.filter(news_item_id=post_id).exists():
            return False
        
        # Parse entry date or use today
        entry_date_str = row.get('news_item_entry_date', '').strip()
        if entry_date_str:
            try:
                # Try parsing common date formats
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y']:
                    try:
                        entry_date = datetime.strptime(entry_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    entry_date = timezone.now().date()
            except:
                entry_date = timezone.now().date()
        else:
            entry_date = timezone.now().date()

        # Generate slug
        slug = slugify(short_title)
        if not slug:
            slug = f"news-{post_id}"
        
        # Handle category if present
        category_name = row.get('category', '').strip()
        
        if dry_run:
            self.stdout.write(f"📰 Would restore: {short_title[:50]}... (ID: {post_id})")
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
        
        # Handle category
        if category_name:
            category, created = NewsItemCategory.objects.get_or_create(
                name=category_name,
                defaults={'slug': slugify(category_name)}
            )
            news_item.category = category
            news_item.save()

        # Handle image if present
        image_url = row.get('wpcf-news-item-image', '').strip()
        if image_url and image_url.startswith('http'):
            self.download_and_attach_image(news_item, image_url)

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
                
        except Exception as e:
            pass  # Silent fail for image downloads