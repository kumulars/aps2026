import csv
import os
from django.core.management.base import BaseCommand
from home.models import NewsResearchItem, NewsItemCategory


class Command(BaseCommand):
    help = 'Assign categories to news items based on archived CSV data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be assigned without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Category mapping from old to new
        category_mapping = {
            'Computational Peptide Science': 'Computational',
            'Structural Biology': 'Structure',
            'Cell Signaling and Cancer': 'Biology',
            'Peptide Materials': 'Materials',
            'Other': 'Other',  # We'll handle this separately
            'Therapeutics and Drug Delivery': 'Therapeutics',
            'Synthetic Methods': 'Synthesis',
        }
        
        # Load category assignments from archived CSV
        csv_file = 'import_files/archive/APS-News-Categorized.csv'
        if not os.path.exists(csv_file):
            self.stdout.write(
                self.style.ERROR(f'Archived CSV file not found: {csv_file}')
            )
            return
        
        category_assignments = {}  # title -> category
        
        with open(csv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                title = row.get('news_item_short_title', '').strip()
                old_category = row.get('category', '').strip()
                
                if title and old_category and len(old_category) < 50 and not old_category.startswith('<'):
                    # Map to new category
                    new_category = category_mapping.get(old_category)
                    if new_category and new_category != 'Other':  # Skip 'Other' for now
                        category_assignments[title] = new_category
        
        self.stdout.write(f"Found {len(category_assignments)} category assignments from CSV")
        
        # Apply assignments to database items
        assigned_count = 0
        not_found_count = 0
        
        # Get category objects
        categories = {cat.name: cat for cat in NewsItemCategory.objects.all()}
        
        if dry_run:
            self.stdout.write("\n🔍 DRY RUN - Would make these assignments:")
        
        for title, new_category in category_assignments.items():
            # Find matching news item (excluding the 14 new ones)
            news_item = NewsResearchItem.objects.filter(
                news_item_short_title=title
            ).exclude(
                news_item_id__startswith='import-'
            ).first()
            
            if news_item:
                if dry_run:
                    self.stdout.write(f"  {title[:40]:40s} → {new_category}")
                else:
                    if new_category in categories:
                        news_item.category = categories[new_category]
                        news_item.save()
                        assigned_count += 1
                        
                        if assigned_count % 20 == 0:
                            self.stdout.write(f"  Assigned {assigned_count} categories...")
                    else:
                        self.stdout.write(f"  ⚠️  Category '{new_category}' not found in database")
            else:
                not_found_count += 1
                if dry_run and not_found_count <= 5:  # Show first few
                    self.stdout.write(f"  ⚠️  Item not found: {title[:40]}...")
        
        if dry_run:
            self.stdout.write(f"\n Would assign {len(category_assignments)} categories")
            self.stdout.write(f" Items not found in database: {not_found_count}")
        else:
            # Final verification
            total_with_categories = NewsResearchItem.objects.exclude(category__isnull=True).count()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Category assignment complete!\n'
                    f'   Successfully assigned: {assigned_count}\n'
                    f'   Items not found: {not_found_count}\n'
                    f'   Total items with categories: {total_with_categories}'
                )
            )
            
            # Show category distribution
            self.stdout.write("\n📊 Final category distribution:")
            for cat_name in ['Synthesis', 'Therapeutics', 'Biology', 'Structure', 'Materials', 'Computational']:
                count = NewsResearchItem.objects.filter(category__name=cat_name).count()
                self.stdout.write(f"   {cat_name}: {count}")