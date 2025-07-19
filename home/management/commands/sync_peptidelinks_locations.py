"""
Enhanced Django management command to sync researcher locations from peptidelinks.net
Usage: python manage.py sync_peptidelinks_locations
"""

import requests
from bs4 import BeautifulSoup
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from home.models import Researcher
from difflib import SequenceMatcher


class Command(BaseCommand):
    help = 'Sync researcher locations by parsing peptidelinks.net structure'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--state',
            type=str,
            help='Only process researchers for a specific state (e.g., "CA")',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )
    
    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.target_state = options.get('state')
        self.verbose = options['verbose']
        
        self.stdout.write('🔄 Fetching data from peptidelinks.net...')
        
        try:
            # Fetch the website
            response = requests.get('https://peptidelinks.net/', timeout=30)
            response.raise_for_status()
            
            if self.verbose:
                self.stdout.write(f'✅ Website fetch successful. Status: {response.status_code}')
                self.stdout.write(f'📊 Content length: {len(response.content)} bytes')

            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Parse the researcher data
            researchers_data = self.parse_researchers_from_website(soup)
            
            # Filter by state if specified
            if self.target_state:
                researchers_data = {k: v for k, v in researchers_data.items() 
                                 if v['state_province'] == self.target_state}
                self.stdout.write(f'🔍 Filtering for {self.target_state}: {len(researchers_data)} researchers found')
            
            # Update the database
            updated_count = self.update_database(researchers_data)
            
            if self.dry_run:
                self.stdout.write(
                    self.style.WARNING(f'🧪 DRY RUN: Would update {updated_count} researchers')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Successfully updated {updated_count} researchers')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error: {str(e)}')
            )
    
    def parse_researchers_from_website(self, soup):
        """Parse researcher data from peptidelinks.net HTML structure"""
        researchers = {}
        
        # Get all text content and look for the specific structure
        text_content = soup.get_text()
        
        # Split by lines and clean up
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        if self.verbose:
            self.stdout.write(f"📋 Total lines found: {len(lines)}")
        
        # US State patterns (all caps followed by researchers)
        us_states = {
            'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
            'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
            'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
            'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
            'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
            'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
            'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
            'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
            'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
            'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
            'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
            'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
            'WISCONSIN': 'WI', 'WYOMING': 'WY'
        }
        
        current_state = None
        current_country = 'USA'
        
        # Look for links that contain researcher information
        all_links = soup.find_all('a', href=True)
        
        # Process each link and its context
        for link in all_links:
            href = link.get('href', '')
            name = link.get_text().strip()
            
            # Skip non-researcher links
            if not href.startswith('http') or len(name) < 3:
                continue
            if any(skip in href.lower() for skip in ['pubmed', 'ncbi', 'mailto', 'javascript']):
                continue
            if any(skip in name.lower() for skip in ['pubmed', 'cv', 'home', 'back', 'top']):
                continue
            
            # Get the context around this link
            context = self.get_link_context(link)
            
            # Check if we're in a new state section
            context_upper = context.upper()
            for state_name, state_abbrev in us_states.items():
                if state_name in context_upper:
                    current_state = state_abbrev
                    current_country = 'USA'
                    if self.verbose:
                        self.stdout.write(f'📍 Found state section: {state_name} ({state_abbrev})')
                    break
            
            # Check for Canada section
            if 'CANADA' in context_upper:
                current_state = 'Canada'
                current_country = 'Canada'
                if self.verbose:
                    self.stdout.write(f'📍 Found Canada section')
            
            # Check for international section
            if 'INTERNATIONAL' in context_upper or 'OTHER COUNTRIES' in context_upper:
                current_country = 'International'
                current_state = None
                if self.verbose:
                    self.stdout.write(f'📍 Found international section')
            
            # Extract researcher information
            if current_state and len(name) > 3:
                institution = self.extract_institution_from_context(context, name)
                
                if institution and institution != "Unknown":
                    # Parse the name
                    name_parts = name.split()
                    if len(name_parts) >= 2:
                        first_name = ' '.join(name_parts[:-1])
                        last_name = name_parts[-1]
                        
                        # Create unique key
                        key = f"{first_name} {last_name}"
                        
                        researchers[key] = {
                            'first_name': first_name,
                            'last_name': last_name,
                            'institution': institution,
                            'website_url': href,
                            'state_province': current_state,
                            'country': current_country
                        }
        
        self.stdout.write(f'📊 Parsed {len(researchers)} researchers from website')
        
        # Show sample for verification
        if self.verbose:
            self.stdout.write("\n📋 Sample researchers:")
            for i, (name, data) in enumerate(list(researchers.items())[:5]):
                self.stdout.write(f"  {i+1}. {name} - {data['institution']} ({data['state_province']})")
        
        return researchers
    
    def get_link_context(self, link):
        """Get the textual context around a link"""
        context_parts = []
        
        # Get parent context
        parent = link.parent
        while parent and len(context_parts) < 3:
            if parent.name in ['p', 'div', 'td', 'li']:
                context_parts.append(parent.get_text())
                break
            parent = parent.parent
        
        # Get next sibling context
        next_sibling = link.next_sibling
        if next_sibling:
            if hasattr(next_sibling, 'get_text'):
                context_parts.append(next_sibling.get_text())
            else:
                context_parts.append(str(next_sibling))
        
        return ' '.join(context_parts)
    
    def extract_institution_from_context(self, context, name):
        """Extract institution name from context"""
        # Remove the researcher name from context
        context_clean = context.replace(name, '')
        
        # Look for institution patterns
        institution_patterns = [
            r'([^,;]+(?:University|Institute|College|School|Laboratory|Lab|Hospital|Medical|Academy|Foundation|Corporation|Company|Inc\.|LLC)[^,;]*)',
            r'([^,;]+(?:Univ|Inst|Corp|Med|Hosp)[^,;]*)',
        ]
        
        for pattern in institution_patterns:
            match = re.search(pattern, context_clean, re.IGNORECASE)
            if match:
                institution = match.group(1).strip()
                # Clean up common artifacts
                institution = re.sub(r'^[,;.\s]+', '', institution)
                institution = re.sub(r'[,;.\s]+$', '', institution)
                if len(institution) > 5:  # Minimum reasonable length
                    return institution
        
        # Fallback: look for anything that looks like an institution
        parts = [p.strip() for p in re.split(r'[,;]', context_clean) if p.strip()]
        for part in parts:
            if len(part) > 10 and any(word in part.lower() for word in 
                                     ['university', 'institute', 'college', 'school', 'laboratory', 'hospital']):
                return part
        
        return "Unknown"
    
    def similarity(self, a, b):
        """Calculate similarity between two strings"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def update_database(self, researchers_data):
        """Update researchers in the database with location data"""
        updated_count = 0
        
        with transaction.atomic():
            for name, data in researchers_data.items():
                # Try to find matching researchers in database
                matches = []
                
                # 1. Exact name match
                exact_matches = Researcher.objects.filter(
                    first_name__iexact=data['first_name'],
                    last_name__iexact=data['last_name']
                )
                matches.extend(exact_matches)
                
                # 2. If no exact match, try fuzzy matching on last name + institution
                if not matches:
                    last_name_matches = Researcher.objects.filter(
                        last_name__iexact=data['last_name']
                    )
                    
                    # Check institution similarity
                    for researcher in last_name_matches:
                        if self.similarity(researcher.institution, data['institution']) > 0.6:
                            matches.append(researcher)
                
                # 3. If still no match, try just last name with high similarity
                if not matches:
                    last_name_matches = Researcher.objects.filter(
                        last_name__iexact=data['last_name']
                    )
                    
                    for researcher in last_name_matches:
                        if self.similarity(researcher.first_name, data['first_name']) > 0.8:
                            matches.append(researcher)
                
                # Update matches that have unknown/empty location
                for researcher in matches:
                    needs_update = (
                        not researcher.state_province or 
                        researcher.state_province.lower() in ['unknown', 'unknown state', ''] or
                        not researcher.country or
                        researcher.country.lower() in ['unknown', '']
                    )
                    
                    if needs_update:
                        if self.dry_run:
                            self.stdout.write(
                                f'Would update: {researcher.first_name} {researcher.last_name} '
                                f'({researcher.institution}) -> {data["state_province"]}, {data["country"]}'
                            )
                        else:
                            researcher.state_province = data['state_province']
                            researcher.country = data['country']
                            
                            # Update website if empty
                            if not researcher.website_url and data.get('website_url'):
                                researcher.website_url = data['website_url']
                            
                            researcher.save()
                            
                            self.stdout.write(
                                f'✅ Updated: {researcher.first_name} {researcher.last_name} '
                                f'-> {data["state_province"]}, {data["country"]}'
                            )
                        
                        updated_count += 1
                        break  # Only update first match to avoid duplicates
        
        return updated_count