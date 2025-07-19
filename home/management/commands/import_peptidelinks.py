from django.core.management.base import BaseCommand
from home.models import PeptideLinksIndexPage, Researcher, ResearchArea
import requests
from bs4 import BeautifulSoup
import re
import time

class Command(BaseCommand):
    help = 'Comprehensive import of all researchers from peptidelinks.net'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting comprehensive import...")
        
        # Get the page content
        response = requests.get('https://peptidelinks.net', timeout=30)
        self.stdout.write(f"✅ Fetched {len(response.text)} characters")
        
        # Parse with more detailed analysis
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Debug: Show the structure
        self.stdout.write("🔍 Analyzing page structure...")
        
        # Look for different types of containers
        all_links = soup.find_all('a', href=True)
        researcher_links = []
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text().strip()
            
            # Skip non-researcher links
            if any(skip in href.lower() for skip in ['pubmed', 'ncbi', 'mailto', 'javascript', '#']):
                continue
            if any(skip in text.lower() for skip in ['pubmed', 'cv', 'home', 'back', 'top']):
                continue
            if not href.startswith('http'):
                continue
            if len(text) < 3:
                continue
            
            # This looks like a researcher link
            researcher_links.append({
                'name': text,
                'url': href,
                'context': link.parent.get_text() if link.parent else ''
            })
        
        self.stdout.write(f"📊 Found {len(researcher_links)} potential researcher links")
        
        # Process each researcher
        researchers = []
        for link_info in researcher_links:
            researcher = self.extract_researcher_info(link_info)
            if researcher:
                researchers.append(researcher)
        
        self.stdout.write(f"📊 Parsed {len(researchers)} researchers")
        
        # Show sample for verification
        self.stdout.write("\n📋 Sample researchers:")
        for i, r in enumerate(researchers[:5]):
            self.stdout.write(f"  {i+1}. {r['name']} - {r['institution']} ({r['location']})")
        
        # Import them
        count = 0
        for r in researchers:
            # Split name
            name_parts = r['name'].split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            
            # Create researcher
            researcher, created = Researcher.objects.get_or_create(
                first_name=first_name,
                last_name=last_name,
                institution=r['institution'],
                defaults={
                    'website_url': r['website'] or '',
                    'pubmed_url': r['pubmed_link'] or '',
                    'country': self.determine_country(r['location']),
                    'state_province': r['location'] if r['location'] not in ['Unknown', 'International'] else ''
                }
            )
            
            if created:
                count += 1
                if count % 25 == 0:
                    self.stdout.write(f"✅ Imported {count}...")
        
        self.stdout.write(f"🎉 Imported {count} new researchers!")
        self.stdout.write(f"📊 Total in database: {Researcher.objects.count()}")
        
    def extract_researcher_info(self, link_info):
        """Extract researcher information from link context"""
        name = link_info['name']
        url = link_info['url']
        context = link_info['context']
        
        # Extract institution and location from context
        institution = "Unknown"
        location = "Unknown"
        pubmed_link = None
        
        # Look for institution patterns in the context
        # Common patterns: "Name, Institution, Location" or "Name (Institution)"
        if ',' in context:
            parts = [p.strip() for p in context.split(',')]
            for i, part in enumerate(parts):
                if name in part:
                    # Institution is usually right after the name
                    if i + 1 < len(parts):
                        potential_institution = parts[i + 1]
                        if any(word in potential_institution.lower() for word in 
                               ['university', 'institute', 'college', 'school', 'laboratory', 'lab']):
                            institution = potential_institution
                            
                            # Location might be the next part
                            if i + 2 < len(parts):
                                location = parts[i + 2]
                    break
        
        # Alternative: look for parentheses
        if institution == "Unknown" and '(' in context and ')' in context:
            paren_content = re.search(r'\(([^)]+)\)', context)
            if paren_content:
                potential_institution = paren_content.group(1)
                if any(word in potential_institution.lower() for word in 
                       ['university', 'institute', 'college', 'school']):
                    institution = potential_institution
        
        # Try to extract location from common patterns
        location = self.extract_location(context, name)
        
        # Look for PubMed link in nearby text
        pubmed_pattern = r'https://www\.ncbi\.nlm\.nih\.gov/pubmed/[^\s<>]+'
        pubmed_match = re.search(pubmed_pattern, context)
        if pubmed_match:
            pubmed_link = pubmed_match.group()
        
        return {
            'name': name,
            'institution': institution,
            'location': location,
            'website': url,
            'pubmed_link': pubmed_link
        }
    
    def extract_location(self, context, name):
        """Extract location from context"""
        # Common US states and abbreviations
        us_states = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
            'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
            'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
            'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
            'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
            'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
            'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
            'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
            'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
            'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
            'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
            'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
            'wisconsin': 'WI', 'wyoming': 'WY'
        }
        
        context_lower = context.lower()
        
        # Check for state names
        for state, abbrev in us_states.items():
            if state in context_lower:
                return abbrev
        
        # Check for state abbreviations
        for abbrev in us_states.values():
            if f' {abbrev} ' in context or f' {abbrev},' in context:
                return abbrev
        
        # Check for countries
        countries = ['canada', 'uk', 'united kingdom', 'germany', 'france', 'japan', 
                    'china', 'australia', 'italy', 'spain', 'israel', 'switzerland']
        
        for country in countries:
            if country in context_lower:
                return country.title()
        
        return "Unknown"
    
    def determine_country(self, location):
        """Determine country from location"""
        if location in ['Unknown']:
            return 'USA'  # Default
        
        # US states
        us_states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
                    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
                    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
                    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
        
        if location in us_states:
            return 'USA'
        elif location.lower() in ['canada']:
            return 'Canada'
        elif location.lower() in ['uk', 'united kingdom']:
            return 'United Kingdom'
        else:
            return location if location != 'Unknown' else 'USA'