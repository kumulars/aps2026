"""
Update PubMed links for all researchers by searching PubMed individually.
Usage: python manage.py update_pubmed_links [--dry-run] [--limit N]
"""

from django.core.management.base import BaseCommand
from home.models import Researcher
import requests
from bs4 import BeautifulSoup
import time
import logging
import re
from urllib.parse import quote, urljoin

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update PubMed links for researchers by searching PubMed'
    
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
        parser.add_argument(
            '--start-id',
            type=int,
            help='Start from specific researcher ID'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of researchers to process before pausing'
        )
    
    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.limit = options.get('limit')
        self.start_id = options.get('start_id', 1)
        self.batch_size = options['batch_size']
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write('Starting PubMed link updates...\n')
        
        # Get researchers to process
        researchers = Researcher.objects.filter(
            id__gte=self.start_id
        ).order_by('id')
        
        if self.limit:
            researchers = researchers[:self.limit]
        
        total = researchers.count()
        self.stdout.write(f'Processing {total} researchers...\n')
        
        # Process in batches
        updated_count = 0
        error_count = 0
        
        for i, researcher in enumerate(researchers, 1):
            try:
                self.stdout.write(f'[{i}/{total}] Processing: {researcher.display_name}', ending='')
                
                # Search PubMed for this researcher
                pubmed_url = self.search_pubmed(researcher)
                
                if pubmed_url:
                    if not self.dry_run:
                        # Update the researcher record
                        researcher.pubmed_url = pubmed_url
                        researcher.save(update_fields=['pubmed_url'])
                        updated_count += 1
                        self.stdout.write(self.style.SUCCESS(f' ✓ Updated: {pubmed_url}'))
                    else:
                        self.stdout.write(self.style.SUCCESS(f' ✓ Would update: {pubmed_url}'))
                        updated_count += 1
                else:
                    self.stdout.write(self.style.WARNING(' ⚠ No PubMed results found'))
                
                # Pause between batches to be respectful to PubMed
                if i % self.batch_size == 0 and i < total:
                    self.stdout.write(f'\nPausing for 3 seconds... ({i}/{total} completed)')
                    time.sleep(3)
                
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f' ❌ Error: {str(e)}'))
                logger.error(f'Error processing researcher {researcher.id}: {e}')
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'✓ Successfully processed: {updated_count}'))
        if error_count:
            self.stdout.write(self.style.ERROR(f'❌ Errors: {error_count}'))
        self.stdout.write('='*50)
        
        if not self.dry_run:
            self.stdout.write('\nRun the export command to generate updated CSV:')
            self.stdout.write('python export_researchers.py')
    
    def search_pubmed(self, researcher):
        """
        Search PubMed for a researcher and return their profile URL if found.
        """
        try:
            # Clean names for search
            first_name = self.clean_name(researcher.first_name)
            last_name = self.clean_name(researcher.last_name)
            
            if not first_name or not last_name:
                return None
            
            # Construct search query
            # PubMed author search format: "Last Name, First Initial"[Author]
            first_initial = first_name[0].upper()
            search_query = f'"{last_name}, {first_initial}"[Author]'
            
            # Add institution if available for better matching
            if researcher.institution:
                institution_words = self.extract_institution_keywords(researcher.institution)
                if institution_words:
                    search_query += f' AND {institution_words}'
            
            # Search PubMed
            search_url = 'https://pubmed.ncbi.nlm.nih.gov/'
            params = {
                'term': search_query,
                'format': 'abstract',
                'size': '20'
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; APS-Research-Bot/1.0; +https://americanpeptidesociety.org/)'
            }
            
            # First, get search results
            response = requests.get(search_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            if 'No results were found' in response.text:
                # Try alternative search without institution
                params['term'] = f'"{last_name}, {first_initial}"[Author]'
                response = requests.get(search_url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
            
            # Parse results and look for author profile links
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for author profile links in search results
            author_links = soup.find_all('a', href=re.compile(r'/.*author.*'))
            
            # Also try to construct a direct author search URL
            if author_links:
                # Get the first author profile link
                author_link = author_links[0]
                profile_url = urljoin('https://pubmed.ncbi.nlm.nih.gov/', author_link.get('href'))
                return profile_url
            else:
                # Construct a general search URL as fallback
                search_term = quote(f'"{last_name} {first_initial}"[Author]')
                fallback_url = f'https://pubmed.ncbi.nlm.nih.gov/?term={search_term}'
                
                # Verify the search returns results
                verify_response = requests.get(fallback_url, headers=headers, timeout=5)
                if verify_response.status_code == 200 and 'No results were found' not in verify_response.text:
                    return fallback_url
            
            return None
            
        except requests.exceptions.RequestException as e:
            logger.warning(f'Request error for {researcher.display_name}: {e}')
            return None
        except Exception as e:
            logger.error(f'Error searching PubMed for {researcher.display_name}: {e}')
            return None
    
    def clean_name(self, name):
        """Clean name for PubMed search."""
        if not name:
            return ""
        
        # Remove common prefixes and suffixes
        name = re.sub(r'\b(Dr\.?|Prof\.?|PhD\.?|MD\.?|Jr\.?|Sr\.?)\b', '', name, flags=re.IGNORECASE)
        
        # Remove extra whitespace and punctuation
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Take first name only (before any spaces)
        name_parts = name.split()
        return name_parts[0] if name_parts else ""
    
    def extract_institution_keywords(self, institution):
        """Extract searchable keywords from institution name."""
        if not institution:
            return ""
        
        # Common institution keywords that help with PubMed matching
        keywords = []
        
        # University names
        if 'university' in institution.lower():
            # Extract university name
            university_match = re.search(r'(\w+)\s+university', institution, re.IGNORECASE)
            if university_match:
                keywords.append(university_match.group(1))
        
        # Institute names
        if 'institute' in institution.lower():
            institute_match = re.search(r'(\w+)\s+institute', institution, re.IGNORECASE)
            if institute_match:
                keywords.append(institute_match.group(1))
        
        # Medical centers, hospitals
        if any(term in institution.lower() for term in ['medical', 'hospital', 'clinic']):
            medical_match = re.search(r'(\w+)\s+(?:medical|hospital|clinic)', institution, re.IGNORECASE)
            if medical_match:
                keywords.append(medical_match.group(1))
        
        # Companies
        if any(term in institution.lower() for term in ['inc', 'corp', 'company', 'pharmaceut']):
            # For companies, just use a general term
            keywords.append('company')
        
        return ' AND '.join(f'"{keyword}"[Affiliation]' for keyword in keywords[:2])  # Limit to 2 keywords
    
    def rate_limit_pause(self):
        """Pause to respect PubMed rate limits."""
        time.sleep(0.5)  # 500ms pause between requests