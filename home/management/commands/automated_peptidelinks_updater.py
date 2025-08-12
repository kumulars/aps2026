"""
Comprehensive automated PeptideLinks updater with Unicode support
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from home.models import Researcher, ResearchArea
import hashlib
import unicodedata
from urllib.parse import urljoin, quote
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Automated PeptideLinks updater with Unicode support and change detection'
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; APS-PeptideLinks-Bot/1.0; +https://www.americanpeptidesociety.org)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,de;q=0.8,fr;q=0.7',
            'Accept-Encoding': 'gzip, deflate',
            'Accept-Charset': 'utf-8, iso-8859-1;q=0.5',
            'Connection': 'keep-alive',
        })
        
    def add_arguments(self, parser):
        parser.add_argument(
            '--force-update',
            action='store_true',
            help='Force update even if no changes detected',
        )
        parser.add_argument(
            '--check-links',
            action='store_true',
            help='Validate researcher website links',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--email-report',
            action='store_true',
            help='Send email report of changes',
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting automated PeptideLinks update...")
        
        start_time = timezone.now()
        stats = {
            'total_found': 0,
            'new_researchers': 0,
            'updated_researchers': 0,
            'removed_researchers': 0,
            'broken_links': 0,
            'fixed_unicode': 0,
        }
        
        try:
            # Step 1: Check if source has changed
            if not options['force_update'] and not self.has_source_changed():
                self.stdout.write("✅ No changes detected in source. Skipping update.")
                return
            
            # Step 2: Fetch and parse current data
            researchers_data = self.fetch_researchers_with_unicode_support()
            stats['total_found'] = len(researchers_data)
            
            if not researchers_data:
                self.stdout.write(self.style.ERROR("❌ No researchers found. Check source availability."))
                return
                
            # Step 3: Process updates
            if not options['dry_run']:
                with transaction.atomic():
                    new_count, updated_count, fixed_unicode = self.update_researchers(researchers_data)
                    stats['new_researchers'] = new_count
                    stats['updated_researchers'] = updated_count
                    stats['fixed_unicode'] = fixed_unicode
            else:
                self.show_dry_run_preview(researchers_data)
                
            # Step 4: Link validation (if requested)
            if options['check_links']:
                stats['broken_links'] = self.validate_researcher_links()
                
            # Step 5: Generate report
            duration = timezone.now() - start_time
            self.generate_report(stats, duration)
            
            # Step 6: Send email report (if requested)
            if options['email_report'] and not options['dry_run']:
                self.send_email_report(stats, duration)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Update failed: {str(e)}"))
            logger.exception("Automated update failed")
            raise

    def fetch_researchers_with_unicode_support(self):
        """Fetch researchers with proper Unicode/UTF-8 handling"""
        self.stdout.write("📡 Fetching data with Unicode support...")
        
        try:
            # Request with explicit UTF-8 encoding support
            response = self.session.get(
                'https://peptidelinks.net', 
                timeout=30,
                stream=True
            )
            response.raise_for_status()
            
            # Force UTF-8 encoding to handle international characters
            response.encoding = 'utf-8'
            
            # Parse with Unicode support
            soup = BeautifulSoup(
                response.text, 
                'html.parser',
                from_encoding='utf-8'
            )
            
            # Extract researchers with proper character handling
            researchers = self.parse_researchers_with_unicode(soup)
            
            self.stdout.write(f"✅ Found {len(researchers)} researchers with proper Unicode support")
            return researchers
            
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to fetch data: {e}"))
            return []

    def parse_researchers_with_unicode(self, soup):
        """Parse researchers with proper international character support"""
        researchers_by_location = {}
        
        # Get text content with Unicode normalization
        content = soup.get_text()
        lines = content.split('\n')
        
        current_location = None
        current_researchers = []
        
        for line in lines:
            # Normalize Unicode characters (handles umlauts, accents, etc.)
            line = unicodedata.normalize('NFKC', line.strip())
            
            if not line:
                continue
                
            # Check if this is a location header
            if self.is_location_header(line):
                # Save previous location's researchers
                if current_location and current_researchers:
                    researchers_by_location[current_location] = current_researchers
                
                current_location = line
                current_researchers = []
                self.stdout.write(f"📍 Processing location: {current_location}")
                
            elif current_location and self.looks_like_researcher_entry(line):
                researcher_info = self.parse_researcher_entry_unicode(line, soup)
                if researcher_info:
                    current_researchers.append(researcher_info)
        
        # Don't forget the last location
        if current_location and current_researchers:
            researchers_by_location[current_location] = current_researchers
            
        # Flatten to single list with location info
        all_researchers = []
        for location, researchers in researchers_by_location.items():
            country, state_province = self.parse_location(location)
            for researcher in researchers:
                researcher['parsed_location'] = {
                    'country': country,
                    'state_province': state_province,
                    'location_text': location
                }
                all_researchers.append(researcher)
                
        return all_researchers

    def parse_researcher_entry_unicode(self, line, soup):
        """Parse individual researcher entry with Unicode support"""
        researcher_info = {
            'name': '',
            'institution': '',
            'website_url': '',
            'pubmed_url': '',
        }
        
        # Find corresponding links in HTML with Unicode-aware search
        for link in soup.find_all('a', href=True):
            link_text = unicodedata.normalize('NFKC', link.get_text().strip())
            href = link.get('href', '')
            
            # Check if this link text appears in our line
            if link_text and link_text in line:
                # Skip old PubMed URLs - we'll generate proper ones
                if 'pubmed' in href.lower() or 'ncbi' in href.lower():
                    pass  # Don't use the old format URLs from source
                elif href.startswith('http') and not researcher_info['website_url']:
                    researcher_info['website_url'] = href
                    researcher_info['name'] = link_text
        
        # Extract institution with Unicode support
        if researcher_info['name']:
            # Clean up the line to extract institution
            remaining = line.replace(researcher_info['name'], '')
            remaining = re.sub(r'PubMed', '', remaining, flags=re.IGNORECASE)
            remaining = re.sub(r'[;,]+', '', remaining).strip()
            
            if remaining:
                # Clean institution name to prevent duplicates
                researcher_info['institution'] = self.clean_institution_name(remaining)
            
            # Generate proper PubMed URL using improved format
            researcher_info['pubmed_url'] = self.create_proper_pubmed_url(researcher_info['name'])
            
            # Generate Google Scholar URL
            researcher_info['google_scholar_url'] = self.create_google_scholar_url(researcher_info['name'])
                
        return researcher_info if researcher_info['name'] else None
    
    def create_proper_pubmed_url(self, full_name):
        """
        Create a proper PubMed search URL for a researcher using the correct format.
        Uses "LastName FirstName"[Author] format for precise matching.
        """
        if not full_name:
            return ''
        
        # Parse name parts
        name_parts = full_name.strip().split()
        if len(name_parts) < 2:
            return ''
        
        # Get first and last name
        first_name = self.clean_name_for_pubmed(name_parts[0])
        last_name = self.clean_name_for_pubmed(' '.join(name_parts[1:]))
        
        if not first_name or not last_name:
            return ''
        
        # Clean names for PubMed search
        first_name_clean = re.sub(r'[^\w\s-]', '', first_name)
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
    
    def clean_name_for_pubmed(self, name):
        """Clean and normalize name for PubMed search."""
        if not name:
            return ""
        
        # Remove titles and suffixes
        name = re.sub(r'\b(Dr\.?|Prof\.?|Professor|PhD\.?|Ph\.D\.?|MD\.?|M\.D\.?|Jr\.?|Sr\.?|II|III)\b', '', name, flags=re.IGNORECASE)
        
        # Remove special characters except hyphens and apostrophes
        name = re.sub(r'[^\w\s\'-]', '', name)
        
        # Clean up whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Handle compound names - take the primary part for first names
        if ' ' in name and len(name.split()) > 1:
            parts = name.split()
            # For first names, take the first part; for last names, keep all parts
            return parts[0] if len(parts[0]) > 1 else name
        
        return name
    
    def create_google_scholar_url(self, full_name):
        """Create a Google Scholar search URL for a researcher"""
        if not full_name:
            return ''
        
        # Clean and format the name for Google Scholar search
        clean_name = full_name.strip()
        
        # Create search term with quotes for exact match
        search_term = f'"{clean_name}"'
        
        # URL encode the search term
        encoded_term = quote(search_term)
        
        # Create the Google Scholar URL
        scholar_url = f'https://scholar.google.com/scholar?q={encoded_term}&hl=en&as_sdt=0%2C5'
        
        return scholar_url
    
    def clean_institution_name(self, institution):
        """Clean institution name to prevent duplicates"""
        if not institution:
            return institution
            
        # Remove exact duplicates (e.g., "University of Georgia University of Georgia")
        words = institution.split()
        if len(words) >= 4:
            # Check if institution name is repeated
            for split_point in range(2, len(words) - 1):
                first_part = ' '.join(words[:split_point])
                remaining = ' '.join(words[split_point:])
                if first_part == remaining:
                    institution = first_part
                    break
                elif remaining.startswith(first_part + ' '):
                    institution = first_part + remaining[len(first_part):].strip()
                    break
        
        # Remove repeated keywords
        keywords = ['University', 'College', 'Institute', 'School']
        for keyword in keywords:
            if institution.count(keyword) > 1:
                # Keep only first occurrence
                parts = institution.split(keyword, 1)
                if len(parts) > 1:
                    after = parts[1]
                    # Remove subsequent occurrences
                    after = after.replace(keyword, '', 1)
                    institution = parts[0] + keyword + after
        
        # Clean extra spaces
        institution = ' '.join(institution.split())
        
        return institution

    def normalize_researcher_name(self, name):
        """Normalize researcher names for comparison (handling Unicode)"""
        if not name:
            return ''
            
        # Normalize Unicode characters
        normalized = unicodedata.normalize('NFKC', name)
        
        # Handle special cases for comparison while preserving original
        # This helps with matching but keeps the proper characters
        return normalized.strip()

    def update_researchers(self, researchers_data):
        """Update researcher database with Unicode support"""
        new_count = 0
        updated_count = 0
        fixed_unicode_count = 0
        
        for researcher_data in researchers_data:
            # Parse name with Unicode support
            name_parts = self.normalize_researcher_name(researcher_data['name']).split(maxsplit=1)
            first_name = name_parts[0] if name_parts else ''
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            if not first_name or not last_name:
                continue
                
            # Check for existing researcher (with fuzzy Unicode matching)
            existing = self.find_existing_researcher(first_name, last_name, researcher_data['institution'])
            
            location = researcher_data.get('parsed_location', {})
            
            researcher_defaults = {
                'website_url': researcher_data.get('website_url', ''),
                'pubmed_url': researcher_data.get('pubmed_url', ''),
                'google_scholar_url': researcher_data.get('google_scholar_url', ''),
                'country': location.get('country', 'USA'),
                'state_province': location.get('state_province', ''),
                'is_active': True,
                'is_verified': True,
                'last_verified': timezone.now(),
            }
            
            if existing:
                # Check if Unicode characters were corrupted and need fixing
                old_first = existing.first_name
                old_last = existing.last_name
                
                # Update with properly encoded names
                updated = False
                for field, value in researcher_defaults.items():
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        updated = True
                
                # Update names with proper Unicode
                if existing.first_name != first_name:
                    existing.first_name = first_name
                    updated = True
                    
                if existing.last_name != last_name:
                    existing.last_name = last_name  
                    updated = True
                
                if updated:
                    existing.save()
                    updated_count += 1
                    
                    # Check if we fixed corrupted Unicode characters
                    if (self.has_corrupted_chars(old_first) or self.has_corrupted_chars(old_last)):
                        fixed_unicode_count += 1
                        self.stdout.write(f"🔧 Fixed Unicode: {old_first} {old_last} → {first_name} {last_name}")
                        
            else:
                # Create new researcher
                Researcher.objects.create(
                    first_name=first_name,
                    last_name=last_name,
                    institution=researcher_data.get('institution', ''),
                    **researcher_defaults
                )
                new_count += 1
                self.stdout.write(f"➕ Added: {first_name} {last_name}")
        
        return new_count, updated_count, fixed_unicode_count

    def has_corrupted_chars(self, text):
        """Check if text contains corrupted Unicode characters"""
        if not text:
            return False
            
        # Common corruption patterns
        corruption_patterns = [
            r'Ã¤',  # corrupted ä
            r'Ã¶',  # corrupted ö
            r'Ã¼',  # corrupted ü
            r'Ã\+',  # general corruption
            r'â€™',  # corrupted apostrophe
            r'â€œ',  # corrupted quotes
            r'Ã©',   # corrupted é
            r'Ã¡',   # corrupted á
            r'\?{2,}',  # multiple question marks (encoding failure)
        ]
        
        return any(re.search(pattern, text) for pattern in corruption_patterns)

    def find_existing_researcher(self, first_name, last_name, institution):
        """Find existing researcher with fuzzy Unicode matching"""
        # Try exact match first
        exact_match = Researcher.objects.filter(
            first_name=first_name,
            last_name=last_name,
            institution=institution
        ).first()
        
        if exact_match:
            return exact_match
            
        # Try fuzzy matching for names with potential Unicode issues
        potential_matches = Researcher.objects.filter(
            first_name__icontains=first_name[:3],  # First 3 chars
            last_name__icontains=last_name[:3],    # First 3 chars  
            institution=institution
        )
        
        # Check each potential match
        for candidate in potential_matches:
            # Use Unicode-aware similarity check
            if self.names_are_similar(first_name, last_name, candidate.first_name, candidate.last_name):
                return candidate
                
        return None

    def names_are_similar(self, new_first, new_last, existing_first, existing_last):
        """Check if names are similar (accounting for Unicode corruption)"""
        # Normalize both sets of names
        new_first_norm = unicodedata.normalize('NFKD', new_first).lower()
        new_last_norm = unicodedata.normalize('NFKD', new_last).lower()
        existing_first_norm = unicodedata.normalize('NFKD', existing_first).lower()
        existing_last_norm = unicodedata.normalize('NFKD', existing_last).lower()
        
        # Remove diacritics for comparison
        new_first_clean = ''.join(c for c in new_first_norm if not unicodedata.combining(c))
        new_last_clean = ''.join(c for c in new_last_norm if not unicodedata.combining(c))
        existing_first_clean = ''.join(c for c in existing_first_norm if not unicodedata.combining(c))
        existing_last_clean = ''.join(c for c in existing_last_norm if not unicodedata.combining(c))
        
        # Check similarity
        first_similar = (new_first_clean == existing_first_clean or 
                        new_first_clean in existing_first_clean or 
                        existing_first_clean in new_first_clean)
        last_similar = (new_last_clean == existing_last_clean or
                       new_last_clean in existing_last_clean or
                       existing_last_clean in new_last_clean)
        
        return first_similar and last_similar

    def has_source_changed(self):
        """Check if the source website has changed since last update"""
        try:
            response = self.session.head('https://peptidelinks.net', timeout=10)
            response.raise_for_status()
            
            # Check Last-Modified header
            last_modified = response.headers.get('Last-Modified')
            etag = response.headers.get('ETag')
            
            # Store/check against previous values (you'd store this in DB)
            # For now, we'll check if it's been more than a week
            return True  # Placeholder - implement proper change detection
            
        except requests.RequestException:
            # If we can't check, assume it changed
            return True

    def is_location_header(self, text):
        """Check if text is a location header (same as before)"""
        # US States
        us_states = [
            'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
            'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
            'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
            'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
            'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
            'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
            'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
            'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
            'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
            'West Virginia', 'Wisconsin', 'Wyoming', 'District of Columbia',
            'Puerto Rico'
        ]
        
        if text in us_states:
            return True
            
        # Countries (usually all caps)
        countries = [
            'AUSTRALIA', 'AUSTRIA', 'BELGIUM', 'BRAZIL', 'CANADA', 'CHINA',
            'DENMARK', 'FINLAND', 'FRANCE', 'GERMANY', 'GREECE', 'HUNGARY',
            'INDIA', 'IRELAND', 'ISRAEL', 'ITALY', 'JAPAN', 'MEXICO',
            'NETHERLANDS', 'NEW ZEALAND', 'NORWAY', 'POLAND', 'PORTUGAL',
            'RUSSIA', 'SINGAPORE', 'SOUTH KOREA', 'SPAIN', 'SWEDEN',
            'SWITZERLAND', 'TAIWAN', 'UNITED KINGDOM', 'UK'
        ]
        
        return text.upper() in countries

    def looks_like_researcher_entry(self, line):
        """Check if line contains researcher information"""
        return (';' in line or ',' in line) and len(line) > 10

    def parse_location(self, location_text):
        """Parse location into country and state/province"""
        us_states = {
            'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
            'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
            'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI', 'Idaho': 'ID',
            'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
            'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
            'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
            'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
            'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
            'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
            'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
            'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT',
            'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
            'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC'
        }
        
        # US States
        if location_text in us_states:
            return 'USA', us_states[location_text]
            
        # Special cases
        if location_text == 'Puerto Rico':
            return 'USA', 'PR'
            
        # International (usually all caps)
        if location_text.upper() == location_text:
            return location_text, ''
            
        # Default
        return 'USA', ''

    def validate_researcher_links(self):
        """Validate researcher website links"""
        self.stdout.write("🔗 Validating researcher links...")
        broken_count = 0
        
        researchers_with_links = Researcher.objects.filter(
            website_url__isnull=False
        ).exclude(website_url='')
        
        def check_single_link(researcher):
            try:
                response = self.session.head(
                    researcher.website_url,
                    timeout=10,
                    allow_redirects=True
                )
                if response.status_code == 200:
                    researcher.website_status = 'active'
                else:
                    researcher.website_status = 'broken'
                    return 1
            except:
                researcher.website_status = 'broken'
                return 1
                
            researcher.last_link_check = timezone.now()
            researcher.save(update_fields=['website_status', 'last_link_check'])
            return 0
        
        # Use threading for faster link checking
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(check_single_link, researcher): researcher 
                for researcher in researchers_with_links[:50]  # Limit for now
            }
            
            for future in as_completed(futures):
                broken_count += future.result()
                
        self.stdout.write(f"🔗 Checked links, found {broken_count} broken")
        return broken_count

    def generate_report(self, stats, duration):
        """Generate update report"""
        self.stdout.write("\n" + "="*60)
        self.stdout.write("📊 UPDATE REPORT")
        self.stdout.write("="*60)
        self.stdout.write(f"Duration: {duration}")
        self.stdout.write(f"Total researchers found: {stats['total_found']}")
        self.stdout.write(f"New researchers added: {stats['new_researchers']}")
        self.stdout.write(f"Researchers updated: {stats['updated_researchers']}")
        self.stdout.write(f"Unicode issues fixed: {stats['fixed_unicode']}")
        if stats.get('broken_links', 0) > 0:
            self.stdout.write(f"Broken links found: {stats['broken_links']}")
        self.stdout.write("="*60)

    def send_email_report(self, stats, duration):
        """Send email report to administrators"""
        if not hasattr(settings, 'ADMINS') or not settings.ADMINS:
            return
            
        subject = f"PeptideLinks Update Report - {datetime.now().strftime('%Y-%m-%d')}"
        message = f"""
PeptideLinks Automated Update Complete

Duration: {duration}
Total researchers found: {stats['total_found']}
New researchers added: {stats['new_researchers']}
Researchers updated: {stats['updated_researchers']}
Unicode issues fixed: {stats['fixed_unicode']}
Broken links found: {stats.get('broken_links', 0)}

Update completed at: {timezone.now()}
        """
        
        admin_emails = [email for name, email in settings.ADMINS]
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                admin_emails,
                fail_silently=False,
            )
            self.stdout.write("📧 Email report sent successfully")
        except Exception as e:
            self.stdout.write(f"📧 Failed to send email report: {e}")

    def show_dry_run_preview(self, researchers_data):
        """Show what would be updated in dry run mode"""
        self.stdout.write("\n🔍 DRY RUN PREVIEW")
        self.stdout.write("="*50)
        
        for i, researcher in enumerate(researchers_data[:10]):
            location = researcher.get('parsed_location', {})
            self.stdout.write(f"{i+1}. {researcher['name']}")
            self.stdout.write(f"   Institution: {researcher.get('institution', 'N/A')}")
            self.stdout.write(f"   Location: {location.get('location_text', 'N/A')}")
            self.stdout.write(f"   Website: {researcher.get('website_url', 'N/A')}")
            self.stdout.write("")
            
        if len(researchers_data) > 10:
            self.stdout.write(f"... and {len(researchers_data) - 10} more researchers")