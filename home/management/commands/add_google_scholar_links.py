"""
Generate Google Scholar search URLs for all researchers.
This creates working search links without needing to scrape Google Scholar.
Usage: python manage.py add_google_scholar_links [--dry-run] [--limit N]
"""

from django.core.management.base import BaseCommand
from home.models import Researcher
import re
from urllib.parse import quote


class Command(BaseCommand):
    help = 'Generate Google Scholar search URLs for all researchers'
    
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
            
            # Create Google Scholar search URL
            scholar_url = self.create_google_scholar_url(first_name, last_name, researcher.institution)
            
            # Show what we're doing
            if dry_run:
                self.stdout.write(f'[{i}/{total}] {researcher.display_name} → {scholar_url}')
            else:
                # Update the researcher
                old_url = researcher.google_scholar_url
                researcher.google_scholar_url = scholar_url
                researcher.save(update_fields=['google_scholar_url'])
                
                if old_url != scholar_url:
                    self.stdout.write(f'[{i}/{total}] ✓ Updated {researcher.display_name}')
                    updated_count += 1
                else:
                    self.stdout.write(f'[{i}/{total}] - No change needed for {researcher.display_name}')
        
        # Summary
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(f'Would update {total} researchers with Google Scholar search URLs')
        else:
            self.stdout.write(self.style.SUCCESS(f'✓ Updated {updated_count} researchers'))
            self.stdout.write('\nTo export updated data, run:')
            self.stdout.write('python export_researchers.py')
        self.stdout.write('='*60)
    
    def clean_name(self, name):
        """Clean and normalize name for Google Scholar search."""
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
    
    def create_google_scholar_url(self, first_name, last_name, institution=None):
        """
        Create a Google Scholar search URL for a researcher.
        Uses advanced search format that works well for academic searches.
        """
        # Clean institution name for better matching
        institution_clean = self.clean_institution(institution) if institution else ""
        
        # Construct search query
        # Format: "First Last" + institution terms for better precision
        author_query = f'"{first_name} {last_name}"'
        
        # Add institution terms if available
        if institution_clean:
            # Extract key institution words (university, college, institute, etc.)
            institution_terms = self.extract_institution_terms(institution_clean)
            if institution_terms:
                search_query = f'{author_query} {institution_terms}'
            else:
                search_query = author_query
        else:
            search_query = author_query
        
        # URL encode the search term
        encoded_query = quote(search_query)
        
        # Create Google Scholar search URL
        # Using the advanced author search which gives better results
        scholar_url = f'https://scholar.google.com/scholar?q={encoded_query}&hl=en&as_sdt=0%2C5'
        
        return scholar_url
    
    def clean_institution(self, institution):
        """Clean institution name for search."""
        if not institution:
            return ""
        
        # Remove common suffixes and prefixes that don't help with search
        institution = re.sub(r'\b(UNITED STATES|FRANCE|GERMANY|CANADA|USA|UK)\b', '', institution, flags=re.IGNORECASE)
        institution = re.sub(r'\b(DEPT\.?|DEPARTMENT)\b', '', institution, flags=re.IGNORECASE)
        
        # Clean up extra spaces
        institution = re.sub(r'\s+', ' ', institution).strip()
        
        return institution
    
    def extract_institution_terms(self, institution):
        """Extract searchable terms from institution name."""
        if not institution:
            return ""
        
        # Look for key institutional terms
        terms = []
        
        # Universities
        university_match = re.search(r'(\w+)\s*(?:university|univ)', institution, re.IGNORECASE)
        if university_match:
            terms.append(university_match.group(1))
        
        # Colleges
        college_match = re.search(r'(\w+)\s*college', institution, re.IGNORECASE)
        if college_match and not university_match:  # Prefer university if both exist
            terms.append(college_match.group(1))
        
        # Institutes
        institute_match = re.search(r'(\w+)\s*(?:institute|inst)', institution, re.IGNORECASE)
        if institute_match and not university_match and not college_match:
            terms.append(institute_match.group(1))
        
        # Medical centers, hospitals
        medical_match = re.search(r'(\w+)\s*(?:medical|hospital|clinic|health)', institution, re.IGNORECASE)
        if medical_match and not terms:  # Only if we don't have other terms
            terms.append(medical_match.group(1))
        
        # Return up to 2 terms to keep search focused
        return ' '.join(terms[:2])
    
    def create_alternative_scholar_url(self, first_name, last_name):
        """Alternative search format for difficult names."""
        # Simple name search without institution
        search_term = f'author:"{first_name} {last_name}"'
        encoded_term = quote(search_term)
        return f'https://scholar.google.com/scholar?q={encoded_term}&hl=en&as_sdt=0%2C5'