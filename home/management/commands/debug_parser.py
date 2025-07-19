"""
Django management command to update researcher locations from peptidelinks.net
Usage: python manage.py update_researcher_locations
"""

import requests
from bs4 import BeautifulSoup
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from home.models import Researcher  # Replace 'myapp' with your actual app name


class Command(BaseCommand):
    help = 'Update researcher locations by scraping peptidelinks.net'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--state',
            type=str,
            help='Only update researchers for a specific state (e.g., "North Carolina")',
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='Show debug information about parsing',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_state = options.get('state')
        debug = options['debug']
        
        self.stdout.write('Fetching data from peptidelinks.net...')
        
        try:
            # Fetch the original website
            response = requests.get('https://peptidelinks.net/', timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if debug:
                self.debug_parsing(soup)
                return
            
            # Parse the researcher data
            researchers_data = self.parse_researchers(soup)
            
            # Filter by state if specified
            if target_state:
                researchers_data = {k: v for k, v in researchers_data.items() 
                                 if v['state'] == target_state}
                self.stdout.write(f'Filtering for {target_state}: {len(researchers_data)} researchers found')
            
            # Update the database
            updated_count = self.update_database(researchers_data, dry_run)
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f'DRY RUN: Would update {updated_count} researchers')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully updated {updated_count} researchers')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )
    
    def debug_parsing(self, soup):
        """Debug the parsing to see what's happening"""
        text_content = soup.get_text()
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        self.stdout.write(f"Total lines found: {len(lines)}")
        self.stdout.write("\nFIRST 20 LINES:")
        for i, line in enumerate(lines[:20]):
            self.stdout.write(f"{i:2}: {line}")
        
        # Look for lines with researcher patterns
        researcher_pattern = re.compile(r'\[([^\]]+)\]\([^)]+\)')
        found_researchers = []
        
        self.stdout.write("\nLOOKING FOR RESEARCHER PATTERNS:")
        for i, line in enumerate(lines):
            if researcher_pattern.search(line):
                found_researchers.append((i, line))
                if len(found_researchers) <= 10:  # Show first 10
                    self.stdout.write(f"Line {i}: {line}")
        
        self.stdout.write(f"\nTotal lines with researcher patterns: {len(found_researchers)}")
        
        # Look for potential state headers
        state_pattern = re.compile(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)*$')
        found_states = []
        
        self.stdout.write("\nLOOKING FOR STATE HEADERS:")
        for i, line in enumerate(lines):
            if (state_pattern.match(line) and 
                len(line) < 30 and
                not line.startswith('PubMed') and 
                line not in ['Upcoming peptide meetings', 'Selected Researchers from Other Countries']):
                found_states.append((i, line))
                if len(found_states) <= 15:  # Show first 15
                    self.stdout.write(f"Line {i}: {line}")
        
        self.stdout.write(f"\nTotal potential state headers: {len(found_states)}")
        
        # Find Alabama specifically and show context
        self.stdout.write("\nSAMPLE CONTENT AROUND ALABAMA:")
        for i, line in enumerate(lines):
            if 'Alabama' in line:
                start = max(0, i-3)
                end = min(len(lines), i+10)
                self.stdout.write(f"Found 'Alabama' at line {i}:")
                for j in range(start, end):
                    marker = " >>> " if j == i else "     "
                    self.stdout.write(f"{marker}{j:2}: {lines[j]}")
                break
    
    def parse_researchers(self, soup):
        """Parse researcher data from the website HTML"""
        researchers = {}
        current_state = None
        
        # Get all text content and split by lines
        text_content = soup.get_text()
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        self.stdout.write(f"Processing {len(lines)} lines...")
        
        # More flexible patterns
        state_pattern = re.compile(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)*$')
        researcher_pattern = re.compile(r'\[([^\]]+)\]\([^)]+\)')  # More flexible pattern
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # Check if this line is a state/country header
            if (state_pattern.match(line) and 
                len(line) < 30 and  # Reasonable length
                not line.startswith('PubMed') and 
                line not in ['Upcoming peptide meetings', 'Selected Researchers from Other Countries']):
                
                current_state = line
                self.stdout.write(f'Processing state: {current_state}')
                
            # Check if this line contains researcher info
            elif current_state and researcher_pattern.search(line):
                # Extract name and institution from the line
                match = researcher_pattern.search(line)
                if match:
                    name = match.group(1).strip()
                    
                    # Try to find institution in the same line
                    # Look for pattern: [Name](url), Institution;
                    institution_match = re.search(r'\]\([^)]+\),\s*([^;]+);', line)
                    if institution_match:
                        institution = institution_match.group(1).strip()
                    else:
                        # Fallback: look for text after the link
                        after_link = line.split(')', 1)
                        if len(after_link) > 1:
                            # Remove leading comma and semicolon stuff
                            institution = re.sub(r'^[,\s]*([^;]+).*', r'\1', after_link[1]).strip()
                        else:
                            institution = "Unknown Institution"
                    
                    # Parse name into first and last
                    name_parts = name.split()
                    if len(name_parts) >= 2:
                        first_name = ' '.join(name_parts[:-1])
                        last_name = name_parts[-1]
                        
                        # Handle special cases
                        if 'David and Jane Richardson' in name:
                            # Handle the Richardson couple case
                            researchers['David Richardson'] = {
                                'first_name': 'David',
                                'last_name': 'Richardson', 
                                'institution': institution,
                                'state': current_state,
                                'country': 'USA' if current_state != 'Canada' else 'Canada'
                            }
                            researchers['Jane Richardson'] = {
                                'first_name': 'Jane',
                                'last_name': 'Richardson',
                                'institution': institution, 
                                'state': current_state,
                                'country': 'USA' if current_state != 'Canada' else 'Canada'
                            }
                        else:
                            researchers[name] = {
                                'first_name': first_name,
                                'last_name': last_name,
                                'institution': institution,
                                'state': current_state,
                                'country': 'USA' if current_state != 'Canada' else 'Canada'
                            }
                            
                        # Debug output for first few researchers
                        if len(researchers) <= 5:
                            self.stdout.write(f"  Found: {name} at {institution}")
            
            i += 1
        
        self.stdout.write(f'Parsed {len(researchers)} researchers from website')
        return researchers
    
    def update_database(self, researchers_data, dry_run=False):
        """Update researchers in the database with location data"""
        updated_count = 0
        
        with transaction.atomic():
            for name, data in researchers_data.items():
                # Try to find matching researchers in database
                # First try exact name match
                matches = Researcher.objects.filter(
                    first_name__iexact=data['first_name'],
                    last_name__iexact=data['last_name']
                )
                
                # If no exact match, try fuzzy matching on last name + institution
                if not matches.exists():
                    matches = Researcher.objects.filter(
                        last_name__iexact=data['last_name'],
                        institution__icontains=data['institution'].split(',')[0].strip()
                    )
                
                # If still no match, try just last name
                if not matches.exists():
                    matches = Researcher.objects.filter(
                        last_name__iexact=data['last_name']
                    )
                
                # Update matches that have unknown/empty location
                for researcher in matches:
                    needs_update = (
                        not researcher.state_province or 
                        researcher.state_province.lower() in ['unknown', 'unknown state', ''] or
                        not researcher.country or
                        researcher.country.lower() in ['unknown', '']
                    )
                    
                    if needs_update:
                        if dry_run:
                            self.stdout.write(
                                f'Would update: {researcher.first_name} {researcher.last_name} '
                                f'-> {data["state"]}, {data["country"]}'
                            )
                        else:
                            # Map state names to abbreviations if needed
                            state_mapping = {
                                'North Carolina': 'NC',
                                'South Carolina': 'SC', 
                                'New York': 'NY',
                                'California': 'CA',
                                'Massachusetts': 'MA',
                                'Pennsylvania': 'PA',
                                'Connecticut': 'CT',
                                'New Jersey': 'NJ',
                                'Maryland': 'MD',
                                'Virginia': 'VA',
                                'Washington': 'WA',
                                'Illinois': 'IL',
                                'Texas': 'TX',
                                'Florida': 'FL',
                                'Ohio': 'OH',
                                'Michigan': 'MI',
                                'Wisconsin': 'WI',
                                'Minnesota': 'MN',
                                'Colorado': 'CO',
                                'Arizona': 'AZ',
                                'Utah': 'UT',
                                'Nevada': 'NV',
                                'Oregon': 'OR',
                                'Washington DC': 'DC',
                                'New Hampshire': 'NH',
                                'Delaware': 'DE',
                                'Tennessee': 'TN',
                                'Kentucky': 'KY',
                                'Louisiana': 'LA',
                                'Alabama': 'AL',
                                'Georgia': 'GA',
                                'Indiana': 'IN',
                                'Iowa': 'IA',
                                'Kansas': 'KS',
                                'Maine': 'ME',
                                'Mississippi': 'MS',
                                'Missouri': 'MO',
                                'Montana': 'MT',
                                'Nebraska': 'NE',
                                'Arkansas': 'AR',
                                'Alaska': 'AK',
                                'Hawaii': 'HI',
                                'Idaho': 'ID',
                                'North Dakota': 'ND',
                                'South Dakota': 'SD',
                                'Rhode Island': 'RI',
                                'Vermont': 'VT',
                                'West Virginia': 'WV',
                                'Wyoming': 'WY'
                            }
                            
                            # Use abbreviation if available, otherwise use full name
                            state_value = state_mapping.get(data['state'], data['state'])
                            
                            researcher.state_province = state_value
                            researcher.country = data['country']
                            researcher.save()
                            
                            self.stdout.write(
                                f'Updated: {researcher.first_name} {researcher.last_name} '
                                f'-> {state_value}, {data["country"]}'
                            )
                        
                        updated_count += 1
        
        return updated_count