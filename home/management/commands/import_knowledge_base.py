"""
Import knowledge base articles from CSV file
Usage: python manage.py import_knowledge_base --csv-file import_files/kb_2_content_export_2025_08_11_18_33_07.csv
"""

import csv
import re
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from django.utils.html import strip_tags
from django.db import transaction
from bs4 import BeautifulSoup

from home.models import KnowledgeBaseArticle, KnowledgeBaseCategory


class Command(BaseCommand):
    help = 'Import knowledge base articles from CSV file'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-file',
            type=str,
            required=True,
            help='Path to the CSV file containing knowledge base articles'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without making changes'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing articles before importing'
        )
    
    def handle(self, *args, **options):
        csv_file = options['csv_file']
        dry_run = options['dry_run']
        clear_existing = options['clear_existing']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made'))
        
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                articles_data = list(reader)
            
            self.stdout.write(f'📚 Found {len(articles_data)} articles in CSV file')
            
            if clear_existing and not dry_run:
                self.stdout.write('🗑️  Clearing existing knowledge base data...')
                KnowledgeBaseArticle.objects.all().delete()
                KnowledgeBaseCategory.objects.all().delete()
                self.stdout.write('✅ Existing data cleared')
            
            # Process in transaction
            if not dry_run:
                with transaction.atomic():
                    imported_count = self.import_articles(articles_data, dry_run)
            else:
                imported_count = self.import_articles(articles_data, dry_run)
            
            self.stdout.write(self.style.SUCCESS(f'✅ Successfully processed {imported_count} articles'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error importing knowledge base: {str(e)}'))
            raise
    
    def import_articles(self, articles_data, dry_run=False):
        imported_count = 0
        categories_created = set()
        
        for i, row in enumerate(articles_data, 1):
            title = row.get('Title', '').strip()
            if not title:
                self.stdout.write(f'⚠️  Skipping row {i}: No title')
                continue
            
            self.stdout.write(f'[{i}/{len(articles_data)}] Processing: {title}')
            
            # Clean and process content
            content = self.clean_html_content(row.get('Content', ''))
            excerpt = self.generate_excerpt(content, row.get('Excerpt', ''))
            
            # Parse date
            published_date = self.parse_date(row.get('Date', ''))
            
            # Parse categories
            categories_list = self.parse_categories(row.get('Categories', ''))
            
            if not dry_run:
                # Create/get categories
                category_objects = []
                for cat_name in categories_list:
                    if cat_name not in categories_created:
                        category, created = KnowledgeBaseCategory.objects.get_or_create(
                            name=cat_name,
                            defaults={'slug': slugify(cat_name)}
                        )
                        if created:
                            self.stdout.write(f'  📁 Created category: {cat_name}')
                            categories_created.add(cat_name)
                    else:
                        category = KnowledgeBaseCategory.objects.get(name=cat_name)
                    category_objects.append(category)
                
                # Create article
                article, created = KnowledgeBaseArticle.objects.get_or_create(
                    title=title,
                    defaults={
                        'slug': slugify(title),
                        'content': content,
                        'excerpt': excerpt,
                        'published_date': published_date,
                        'status': row.get('Status', 'publish').lower(),
                        'tags': row.get('Tags', ''),
                        'import_date': timezone.now(),
                    }
                )
                
                if created:
                    # Add categories
                    article.categories.set(category_objects)
                    self.stdout.write(f'  ✅ Created article: {title}')
                    imported_count += 1
                else:
                    self.stdout.write(f'  ⚠️  Article already exists: {title}')
            else:
                self.stdout.write(f'  📝 Would create: {title}')
                self.stdout.write(f'    Categories: {", ".join(categories_list)}')
                self.stdout.write(f'    Content length: {len(content)} chars')
                imported_count += 1
        
        return imported_count
    
    def clean_html_content(self, html_content):
        """Clean and process HTML content"""
        if not html_content:
            return ''
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove any script or style tags
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Clean up classes and IDs that might be specific to the old system
        for tag in soup.find_all():
            if tag.get('class'):
                # Keep some useful classes but remove system-specific ones
                classes = tag.get('class')
                cleaned_classes = [cls for cls in classes if not cls.startswith('kb-') or cls in ['kb-secondary-header', 'kb-tertiary-header', 'kb-citation']]
                if cleaned_classes:
                    tag['class'] = cleaned_classes
                else:
                    del tag['class']
            if tag.get('id'):
                del tag['id']
        
        # Convert to string and clean up
        content = str(soup)
        
        # Remove extra whitespace
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'>\s+<', '><', content)
        
        return content.strip()
    
    def generate_excerpt(self, content, existing_excerpt=''):
        """Generate excerpt from content"""
        if existing_excerpt.strip():
            return existing_excerpt.strip()
        
        # Extract text from HTML
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text()
        
        # Clean and truncate
        text = ' '.join(text.split())  # Normalize whitespace
        if len(text) > 300:
            text = text[:297] + '...'
        
        return text
    
    def parse_date(self, date_string):
        """Parse date string to datetime"""
        if not date_string:
            return timezone.now()
        
        try:
            # Try to parse the date format from CSV
            return datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.get_current_timezone())
        except ValueError:
            try:
                return datetime.strptime(date_string, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
            except ValueError:
                return timezone.now()
    
    def parse_categories(self, categories_string):
        """Parse categories string into list"""
        if not categories_string:
            return []
        
        categories = [cat.strip() for cat in categories_string.split(',')]
        return [cat for cat in categories if cat]