import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.utils import timezone
from django.utils.dateparse import parse_date
from home.models import NewsResearchItem, NewsItemCategory
from wagtail.images.models import Image
import requests
from django.core.files.base import ContentFile


class Command(BaseCommand):
    help = 'Complete re-import: delete all, import original data, then import 14 new items'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion of all existing news items'
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This will DELETE ALL existing news items and re-import everything.\n'
                    'Run with --confirm to proceed.'
                )
            )
            return

        # Step 1: Delete all existing NewsResearchItem records
        self.stdout.write("🗑️  Deleting all existing NewsResearchItem records...")
        count = NewsResearchItem.objects.count()
        NewsResearchItem.objects.all().delete()
        self.stdout.write(f"   Deleted {count} records")

        # Step 2: Import original data
        self.stdout.write("\n📥 Importing original news data...")
        original_csv = 'import_files/original_news_import.csv'
        
        if not os.path.exists(original_csv):
            self.stdout.write(
                self.style.ERROR(f'Original CSV file not found: {original_csv}')
            )
            return

        original_count = self.import_original_data(original_csv)
        
        # Step 3: Import the 14 new items
        self.stdout.write("\n📥 Importing 14 new items...")
        new_items_csv = 'import_files/backup_14_new_items.csv'
        
        if not os.path.exists(new_items_csv):
            self.stdout.write(
                self.style.ERROR(f'New items CSV file not found: {new_items_csv}')
            )
            return

        new_count = self.import_new_items(new_items_csv)
        
        # Final summary
        total_count = NewsResearchItem.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Complete re-import finished!\n'
                f'   Original items: {original_count}\n'
                f'   New items: {new_count}\n'
                f'   Total in database: {total_count}'
            )
        )

    def import_original_data(self, csv_file):
        """Import from the original CSV with proper IDs and dates"""
        imported_count = 0
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                try:
                    # Handle BOM if present
                    if '\ufeffnews_item_id' in row:
                        row['news_item_id'] = row.pop('\ufeffnews_item_id')
                    
                    # Parse the original numeric ID
                    news_item_id = int(row['news_item_id'])
                    
                    # Parse the original date
                    entry_date = parse_date(row['news_item_entry_date'])
                    if not entry_date:
                        # Try other date formats
                        try:
                            entry_date = datetime.strptime(row['news_item_entry_date'], '%m/%d/%y').date()
                        except:
                            try:
                                entry_date = datetime.strptime(row['news_item_entry_date'], '%m/%d/%Y').date()
                            except:
                                entry_date = timezone.now().date()
                    
                    # Find matching image by filename
                    image = None
                    image_name = row.get('news_item_image_name', '').strip()
                    if image_name:
                        # Try to find image by filename
                        image = Image.objects.filter(file__icontains=image_name.split('.')[0]).first()
                        if not image:
                            # Try to find by title containing the filename
                            image = Image.objects.filter(title__icontains=image_name.split('.')[0]).first()
                    
                    # Create the news item with original data
                    news_item = NewsResearchItem.objects.create(
                        news_item_id=str(news_item_id),  # Convert to string for current model
                        news_item_entry_date=entry_date,
                        news_item_pi_first_name=row['news_item_pi_first_name'].strip(),
                        news_item_pi_last_name=row['news_item_pi_last_name'].strip(),
                        news_item_pi_title=row['news_item_pi_title'].strip(),
                        news_item_pi_institution=row['news_item_pi_institution'].strip(),
                        news_item_pi_website=row['news_item_pi_website'].strip(),
                        news_item_short_title=row['news_item_short_title'].strip(),
                        slug=slugify(row['news_item_short_title'].strip()),
                        news_item_blurb=row['news_item_blurb'].strip(),
                        news_item_full_text=row['news_item_full_text'].strip(),
                        news_item_image_caption='',
                        news_item_full_title=row['news_item_full_title'].strip(),
                        news_item_authors=row['news_item_authors'].strip(),
                        news_item_citation=row['news_item_citation'].strip(),
                        news_item_journal_url=row['news_item_journal_url'].strip(),
                        news_item_image=image,
                    )
                    
                    imported_count += 1
                    if imported_count % 20 == 0:
                        self.stdout.write(f"   Imported {imported_count} original items...")
                        
                except Exception as e:
                    self.stdout.write(f"   ⚠️  Error importing item {row.get('news_item_id', 'unknown')}: {e}")
                    continue
        
        return imported_count

    def import_new_items(self, csv_file):
        """Import the 14 new items"""
        imported_count = 0
        
        # The new item slugs for generating IDs
        new_item_slugs = [
            'conjugation-chemistry',
            'grafted-coiled-coils', 
            'efficient-sirna-delivery',
            'potent-antifungal-lipopeptide',
            'oxidative-peptide-coupling',
            'quorum-sensing-redux',
            'macrocyclic-peptide-antibiotics',
            'rational-design',
            'intracellular-targeting',
            'shaping-peptide-assemblies',
            'delivery-of-peptide-lytac',
            'peptide-anti-obesity-20',
            'conformational-equilibrium',
            'proline-scanning'
        ]
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for i, row in enumerate(reader):
                try:
                    slug = new_item_slugs[i] if i < len(new_item_slugs) else slugify(row['news_item_short_title'])
                    
                    news_item = NewsResearchItem.objects.create(
                        news_item_id=f'import-{slug}',
                        news_item_entry_date=timezone.now().date(),
                        news_item_pi_first_name=row['news_item_pi_first_name'].strip(),
                        news_item_pi_last_name=row['news_item_pi_last_name'].strip(),
                        news_item_pi_title=row['news_item_pi_title'].strip(),
                        news_item_pi_institution=row['news_item_pi_institution'].strip(),
                        news_item_pi_website='',
                        news_item_short_title=row['news_item_short_title'].strip(),
                        slug=slug,
                        news_item_blurb=row['news_item_blurb'].strip(),
                        news_item_full_text=row['news_item_full_text'].strip(),
                        news_item_image_caption=row['news_item_image_caption'].strip(),
                        news_item_full_title=row['news_item_full_title'].strip(),
                        news_item_authors=row['news_item_authors'].strip(),
                        news_item_citation=row['news_item_citation'].strip(),
                        news_item_journal_url=row['news_item_journal_url'].strip(),
                        news_item_image=None,  # No images for new items initially
                    )
                    
                    imported_count += 1
                    
                except Exception as e:
                    self.stdout.write(f"   ⚠️  Error importing new item {i+1}: {e}")
                    continue
        
        return imported_count