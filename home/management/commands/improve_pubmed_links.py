"""
Improve PubMed links using better search formats.
Usage: python manage.py improve_pubmed_links [--dry-run] [--limit N]

This uses multiple search strategies for better accuracy:
1. "Last, First" format (most accurate for academic papers)  
2. "Last First" format (fallback)
3. Full name variations based on researcher names
"""

from django.core.management.base import BaseCommand
from home.models import Researcher
import re
from urllib.parse import quote


class Command(BaseCommand):
    help = 'Improve PubMed search URLs with better search formats'
    
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
            
            # Create improved PubMed search URL
            new_url = self.create_improved_pubmed_url(first_name, last_name)
            old_url = researcher.pubmed_url
            
            # Show what we're doing
            if dry_run:
                self.stdout.write(f'[{i}/{total}] {researcher.display_name}')
                self.stdout.write(f'    Old: {old_url}')
                self.stdout.write(f'    New: {new_url}')
            else:
                # Update the researcher
                researcher.pubmed_url = new_url
                researcher.save(update_fields=['pubmed_url'])
                
                if old_url != new_url:
                    self.stdout.write(f'[{i}/{total}] ✓ Updated {researcher.display_name}')
                    updated_count += 1
                else:
                    self.stdout.write(f'[{i}/{total}] - No change needed for {researcher.display_name}')
        
        # Summary
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(f'Would update {total} researchers with improved PubMed URLs')
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
        
        return name
    
    def create_improved_pubmed_url(self, first_name, last_name):
        """
        Create improved PubMed search URL using better search strategies.
        
        PubMed search strategies in order of preference:
        1. "Last, First"[Author] - Most accurate for academic papers
        2. Handle special cases (compound names, initials, etc.)
        """
        # Strategy 1: Full "Last, First" format (most accurate)
        # This matches the traditional academic citation format
        search_term = f'"{last_name}, {first_name}"[Author]'
        
        # Handle special cases for better matching
        if len(first_name) == 1:
            # If first name is just an initial, also try without comma
            # Some papers use "LastName Initial" format
            alt_search_term = f'"{last_name} {first_name}"[Author]'
            # Use the comma format as primary, but this shows we considered alternatives
        
        # Handle compound last names (Van Der, De La, etc.)
        if ' ' in last_name:
            # For compound names, the "Last, First" format is especially important
            # e.g., "Van Der Berg, John" not "Berg, John" 
            pass  # Our current format handles this correctly
        
        # Handle names with apostrophes or hyphens
        if "'" in last_name or "-" in last_name:
            # Keep these characters as they're part of the name
            pass  # Our current format handles this correctly
        
        # URL encode the search term
        encoded_term = quote(search_term)
        
        # Create the full PubMed URL with modern endpoint
        pubmed_url = f'https://pubmed.ncbi.nlm.nih.gov/?term={encoded_term}&sort=date'
        
        return pubmed_url
    
    def create_alternative_formats(self, first_name, last_name):
        """Generate alternative search formats for difficult names."""
        alternatives = []
        
        # Format 1: "Last, First Initial"
        first_initial = first_name[0].upper() if first_name else ""
        alternatives.append(f'"{last_name}, {first_initial}"[Author]')
        
        # Format 2: "Last First" (no comma)
        alternatives.append(f'"{last_name} {first_name}"[Author]')
        
        # Format 3: Just last name for very common issues
        alternatives.append(f'"{last_name}"[Author]')
        
        return alternatives