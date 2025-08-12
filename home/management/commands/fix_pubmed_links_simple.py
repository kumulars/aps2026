"""
Simple approach: Generate proper PubMed search URLs for each researcher.
This creates working search links without needing to scrape PubMed.
Usage: python manage.py fix_pubmed_links_simple [--dry-run]
"""

from django.core.management.base import BaseCommand
from home.models import Researcher
import re
from urllib.parse import quote


class Command(BaseCommand):
    help = 'Generate proper PubMed search URLs for all researchers'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of researchers to process'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options.get('limit')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Get all researchers
        researchers = Researcher.objects.all().order_by('id')
        if limit:
            researchers = researchers[:limit]
        
        total = researchers.count()
        self.stdout.write(f'Processing {total} researchers...\n')
        
        updated_count = 0
        
        for i, researcher in enumerate(researchers, 1):
            # Clean and format names
            first_name = self.clean_name(researcher.first_name)
            last_name = self.clean_name(researcher.last_name)
            
            if not first_name or not last_name:
                self.stdout.write(f'[{i}/{total}] ⚠️  Skipping {researcher.display_name} - invalid name')
                continue
            
            # Create PubMed search URL
            pubmed_url = self.create_pubmed_search_url(first_name, last_name)
            
            # Show what we're doing
            if dry_run:
                self.stdout.write(f'[{i}/{total}] {researcher.display_name} → {pubmed_url}')
            else:
                # Update the researcher
                old_url = researcher.pubmed_url
                researcher.pubmed_url = pubmed_url
                researcher.save(update_fields=['pubmed_url'])
                
                if old_url != pubmed_url:
                    self.stdout.write(f'[{i}/{total}] ✓ Updated {researcher.display_name}')
                    updated_count += 1
                else:
                    self.stdout.write(f'[{i}/{total}] - No change needed for {researcher.display_name}')
        
        # Summary
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(f'Would update {total} researchers with proper PubMed search URLs')
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Updated {updated_count} researchers'))
            self.stdout.write('\nTo export updated data, run:')
            self.stdout.write('python export_researchers.py')
        self.stdout.write('='*60)
    
    def clean_name(self, name):
        """Clean and normalize name for PubMed search."""
        if not name:
            return ""
        
        # Remove titles and suffixes
        name = re.sub(r'\b(Dr\.?|Prof\.?|Professor|PhD\.?|Ph\.D\.?|MD\.?|M\.D\.?|Jr\.?|Sr\.?|II|III)\b', '', name, flags=re.IGNORECASE)
        
        # Remove special characters except hyphens and apostrophes
        name = re.sub(r'[^\w\s\'-]', '', name)
        
        # Clean up whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Handle compound names - take the primary part
        if ' ' in name:
            parts = name.split()
            # For first names, take the first part
            # For last names, keep all parts (like "Van Der Berg")
            return parts[0] if len(parts[0]) > 1 else name
        
        return name
    
    def create_pubmed_search_url(self, first_name, last_name):
        """
        Create a proper PubMed search URL for a researcher.
        Uses the format: "LastName FirstName"[Author] for more precise matching.
        """
        # Clean the first name for PubMed search
        first_name_clean = re.sub(r'[^\w\s-]', '', first_name) if first_name else ""
        
        # Handle names with special characters
        last_name_clean = re.sub(r'[^\w\s-]', '', last_name)
        
        # Construct search term with full first name
        if first_name_clean:
            search_term = f'"{last_name_clean} {first_name_clean}"[Author]'
        else:
            search_term = f'"{last_name_clean}"[Author]'
        
        # URL encode the search term
        encoded_term = quote(search_term)
        
        # Create the full PubMed URL
        pubmed_url = f'https://pubmed.ncbi.nlm.nih.gov/?term={encoded_term}&sort=date'
        
        return pubmed_url
    
    def create_alternative_search_url(self, first_name, last_name):
        """Alternative search format for difficult names."""
        # Simple name search without author field restriction
        search_term = f'{last_name} {first_name}'
        encoded_term = quote(search_term)
        return f'https://pubmed.ncbi.nlm.nih.gov/?term={encoded_term}&sort=date'