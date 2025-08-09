"""
Fixed import script for peptidelinks.net that properly parses location headers
"""

from django.core.management.base import BaseCommand
from home.models import Researcher, ResearchArea
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime


class Command(BaseCommand):
    help = 'Import researchers from peptidelinks.net with correct location parsing'
    
    # Map of US state names to abbreviations
    US_STATES = {
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
    
    # Canadian provinces
    CANADIAN_PROVINCES = {
        'Alberta': 'AB', 'British Columbia': 'BC', 'Manitoba': 'MB',
        'New Brunswick': 'NB', 'Newfoundland': 'NL', 'Northwest Territories': 'NT',
        'Nova Scotia': 'NS', 'Nunavut': 'NU', 'Ontario': 'ON',
        'Prince Edward Island': 'PE', 'Quebec': 'QC', 'Saskatchewan': 'SK', 'Yukon': 'YT'
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing researchers before importing',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and show data without importing',
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting fixed PeptideLinks import...")
        
        if options['clear'] and not options['dry_run']:
            self.stdout.write("⚠️  Clearing existing researchers...")
            Researcher.objects.all().delete()
            self.stdout.write("✅ Cleared all researchers")
        
        # Fetch the page
        try:
            response = requests.get('https://peptidelinks.net', timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch page: {e}"))
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Parse researchers by location
        researchers_by_location = self.parse_researchers_by_location(soup)
        
        # Show summary
        total = sum(len(researchers) for researchers in researchers_by_location.values())
        self.stdout.write(f"\n📊 Found {total} researchers in {len(researchers_by_location)} locations")
        
        # Show sample data
        self.stdout.write("\n📍 Location breakdown:")
        for location, researchers in list(researchers_by_location.items())[:10]:
            self.stdout.write(f"  {location}: {len(researchers)} researchers")
        
        if options['dry_run']:
            self.stdout.write("\n🔍 Sample researchers:")
            for location, researchers in list(researchers_by_location.items())[:3]:
                self.stdout.write(f"\n{location}:")
                for r in researchers[:2]:
                    self.stdout.write(f"  - {r['name']} | {r['institution']} | {r['website_url'][:50] if r['website_url'] else 'No URL'}")
            return
        
        # Import researchers
        imported = 0
        updated = 0
        errors = 0
        
        for location, researchers in researchers_by_location.items():
            country, state_province = self.parse_location(location)
            
            for researcher_data in researchers:
                try:
                    # Parse name
                    name_parts = researcher_data['name'].split(maxsplit=1)
                    first_name = name_parts[0] if name_parts else ''
                    last_name = name_parts[1] if len(name_parts) > 1 else ''
                    
                    # Create or update researcher
                    researcher, created = Researcher.objects.update_or_create(
                        first_name=first_name,
                        last_name=last_name,
                        institution=researcher_data['institution'],
                        defaults={
                            'website_url': researcher_data['website_url'] or '',
                            'pubmed_url': researcher_data['pubmed_url'] or '',
                            'country': country,
                            'state_province': state_province,
                            'is_active': True,
                            'is_verified': True,
                            'last_verified': datetime.now()
                        }
                    )
                    
                    if created:
                        imported += 1
                    else:
                        updated += 1
                    
                    if (imported + updated) % 50 == 0:
                        self.stdout.write(f"Progress: {imported} imported, {updated} updated...")
                        
                except Exception as e:
                    errors += 1
                    self.stdout.write(self.style.WARNING(f"Error with {researcher_data['name']}: {e}"))
        
        # Final summary
        self.stdout.write(self.style.SUCCESS(f"\n✅ Import complete!"))
        self.stdout.write(f"  📥 Imported: {imported}")
        self.stdout.write(f"  🔄 Updated: {updated}")
        self.stdout.write(f"  ❌ Errors: {errors}")
        self.stdout.write(f"  📊 Total in database: {Researcher.objects.count()}")

    def parse_researchers_by_location(self, soup):
        """Parse researchers grouped by their location headers"""
        researchers_by_location = {}
        current_location = None
        current_researchers = []
        
        # Get the main content area
        content = soup.get_text()
        lines = content.split('\n')
        
        # State/location pattern - lines that are just location names
        location_pattern = re.compile(r'^[A-Z][A-Za-z\s]+$')
        
        # Track which line we're on
        for i, line in enumerate(lines):
            line = line.strip()
            
            if not line:
                continue
            
            # Check if this looks like a location header
            # Location headers are typically just the state/country name on its own line
            if self.is_location_header(line):
                # Save previous location's researchers
                if current_location and current_researchers:
                    researchers_by_location[current_location] = current_researchers
                
                # Start new location
                current_location = line
                current_researchers = []
                self.stdout.write(f"📍 Found location: {current_location}")
            
            # Check if this line contains researcher info
            elif current_location and self.looks_like_researcher(line):
                researcher_info = self.parse_researcher_line(line, soup)
                if researcher_info:
                    current_researchers.append(researcher_info)
        
        # Don't forget the last location
        if current_location and current_researchers:
            researchers_by_location[current_location] = current_researchers
        
        # If the line-based parsing didn't work well, try a different approach
        if len(researchers_by_location) < 10:
            self.stdout.write("⚠️  Line parsing found few locations, trying HTML structure...")
            researchers_by_location = self.parse_by_html_structure(soup)
        
        return researchers_by_location

    def parse_by_html_structure(self, soup):
        """Alternative parsing method using HTML structure"""
        researchers_by_location = {}
        
        # Look for all links that might be researchers
        all_links = soup.find_all('a', href=True)
        
        current_location = "Unknown"
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text().strip()
            
            # Skip non-researcher links
            if 'pubmed' in href.lower() or 'ncbi' in href.lower():
                continue
            if not text or len(text) < 3:
                continue
            if text.lower() in ['home', 'back', 'top', 'cv', 'pubmed']:
                continue
            
            # Check if this might be a researcher
            if self.looks_like_researcher_name(text):
                # Try to determine location from context
                parent_text = link.parent.get_text() if link.parent else ''
                
                # Look for location indicators
                location = self.extract_location_from_context(parent_text)
                if location == "Unknown":
                    # Try looking at previous siblings for headers
                    prev = link.parent.find_previous_sibling() if link.parent else None
                    if prev:
                        prev_text = prev.get_text().strip()
                        if self.is_location_header(prev_text):
                            location = prev_text
                
                if location not in researchers_by_location:
                    researchers_by_location[location] = []
                
                # Extract researcher info
                researcher_info = {
                    'name': text,
                    'website_url': href if href.startswith('http') else '',
                    'institution': self.extract_institution(parent_text, text),
                    'pubmed_url': self.find_nearby_pubmed_link(link)
                }
                
                researchers_by_location[location].append(researcher_info)
        
        return researchers_by_location

    def is_location_header(self, text):
        """Check if text is likely a location header"""
        # US States
        if text in self.US_STATES:
            return True
        
        # Canadian provinces
        if text in self.CANADIAN_PROVINCES:
            return True
        
        # Countries (all caps)
        countries = ['AUSTRALIA', 'AUSTRIA', 'BELGIUM', 'BRAZIL', 'CANADA', 'CHINA', 
                    'DENMARK', 'FINLAND', 'FRANCE', 'GERMANY', 'GREECE', 'HUNGARY',
                    'INDIA', 'IRELAND', 'ISRAEL', 'ITALY', 'JAPAN', 'MEXICO',
                    'NETHERLANDS', 'NEW ZEALAND', 'NORWAY', 'POLAND', 'PORTUGAL',
                    'RUSSIA', 'SINGAPORE', 'SOUTH KOREA', 'SPAIN', 'SWEDEN', 
                    'SWITZERLAND', 'TAIWAN', 'UNITED KINGDOM', 'UK']
        
        if text.upper() in countries:
            return True
        
        # Special cases
        if text in ['District of Columbia', 'Puerto Rico']:
            return True
        
        return False

    def looks_like_researcher(self, line):
        """Check if a line likely contains researcher information"""
        # Researchers usually have names and institutions
        return (';' in line or ',' in line) and len(line) > 10

    def looks_like_researcher_name(self, text):
        """Check if text looks like a person's name"""
        # Simple heuristic: 2-4 words, starts with capital letter
        words = text.split()
        if 2 <= len(words) <= 4:
            if words[0][0].isupper():
                # Avoid common non-name patterns
                if not any(skip in text.lower() for skip in ['university', 'institute', 'college', 'lab']):
                    return True
        return False

    def parse_researcher_line(self, line, soup):
        """Parse a line containing researcher information"""
        # Look for the pattern: Name, Institution; PubMed
        # or: Name (Institution)
        
        researcher_info = {
            'name': '',
            'institution': '',
            'website_url': '',
            'pubmed_url': ''
        }
        
        # Try to find links in the original HTML that match this text
        for link in soup.find_all('a', href=True):
            link_text = link.get_text().strip()
            if link_text in line:
                href = link.get('href', '')
                
                if 'pubmed' in href.lower() or 'ncbi' in href.lower():
                    researcher_info['pubmed_url'] = href
                elif href.startswith('http') and not researcher_info['website_url']:
                    researcher_info['website_url'] = href
                    researcher_info['name'] = link_text
        
        # Extract institution from the line
        if researcher_info['name']:
            # Remove the name and PubMed parts to find institution
            remaining = line.replace(researcher_info['name'], '').replace('PubMed', '')
            remaining = remaining.strip(' ,;')
            
            # Clean up parentheses
            remaining = re.sub(r'[()]', '', remaining)
            
            if remaining:
                researcher_info['institution'] = remaining.strip()
        
        return researcher_info if researcher_info['name'] else None

    def extract_institution(self, text, name):
        """Extract institution from text context"""
        # Remove the name from the text
        text = text.replace(name, '')
        
        # Look for institution patterns
        patterns = [
            r'(?:at|from)\s+([^,;]+)',  # "at University of..."
            r',\s*([^,;]+)',  # After comma
            r'\(([^)]+)\)',  # In parentheses
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                institution = match.group(1).strip()
                # Clean up common suffixes
                institution = institution.replace('; PubMed', '').replace(', PubMed', '')
                if len(institution) > 3:
                    return institution
        
        return ''

    def extract_location_from_context(self, text):
        """Try to extract location from surrounding text"""
        # Check for state abbreviations
        for state, abbrev in self.US_STATES.items():
            if f', {abbrev}' in text or f' {abbrev} ' in text:
                return state
        
        # Check for country names
        countries = ['AUSTRALIA', 'CANADA', 'CHINA', 'FRANCE', 'GERMANY', 'ISRAEL', 
                    'ITALY', 'JAPAN', 'SPAIN', 'SWITZERLAND', 'UK', 'UNITED KINGDOM']
        
        for country in countries:
            if country in text.upper():
                return country
        
        return "Unknown"

    def find_nearby_pubmed_link(self, link_element):
        """Find PubMed link near a researcher link"""
        # Look for next sibling that might be PubMed
        next_elem = link_element.find_next_sibling('a')
        if next_elem:
            href = next_elem.get('href', '')
            if 'pubmed' in href.lower() or 'ncbi' in href.lower():
                return href
        
        # Look in parent for PubMed links
        if link_element.parent:
            for sibling in link_element.parent.find_all('a'):
                href = sibling.get('href', '')
                if 'pubmed' in href.lower() or 'ncbi' in href.lower():
                    return href
        
        return ''

    def parse_location(self, location_text):
        """Parse location text into country and state/province"""
        # US States
        if location_text in self.US_STATES:
            return 'USA', self.US_STATES[location_text]
        
        # Canadian provinces
        if location_text in self.CANADIAN_PROVINCES:
            return 'Canada', self.CANADIAN_PROVINCES[location_text]
        
        # International countries
        if location_text.upper() == location_text:  # All caps = country
            return location_text, ''
        
        # Special cases
        if location_text == 'District of Columbia':
            return 'USA', 'DC'
        if location_text == 'Puerto Rico':
            return 'USA', 'PR'
        
        # Default
        return 'USA', ''