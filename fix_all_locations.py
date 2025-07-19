"""
Save this as: fix_all_locations.py
Run with: python fix_all_locations.py
"""

import os
import django
import requests
from bs4 import BeautifulSoup
import re

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aps2026_site.settings')
django.setup()

from home.models import Researcher

def get_researchers_from_website():
    """Get all researchers with their locations from peptidelinks.net"""
    print("Fetching data from peptidelinks.net...")
    
    response = requests.get('https://peptidelinks.net/', timeout=30)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Get the text content
    text = soup.get_text()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    researchers = {}
    current_state = None
    
    # US state abbreviations mapping
    state_abbrevs = {
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
        'Wisconsin': 'WI', 'Wyoming': 'WY', 'Washington DC': 'DC'
    }
    
    for line in lines:
        # Check if line is a state/country header
        if (re.match(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)*$', line) and 
            len(line) < 30 and
            line not in ['PubMed', 'Upcoming peptide meetings']):
            current_state = line
            print(f"Processing: {current_state}")
            continue
        
        # Look for researcher entries [Name](url), Institution
        if current_state and '[' in line and '](' in line:
            # Extract name from [Name](url) pattern
            name_match = re.search(r'\[([^\]]+)\]', line)
            if name_match:
                full_name = name_match.group(1).strip()
                
                # Extract institution (text between ), and ;)
                inst_match = re.search(r'\]\([^)]+\),\s*([^;]+)', line)
                institution = inst_match.group(1).strip() if inst_match else "Unknown"
                
                # Handle special cases
                if 'David and Jane Richardson' in full_name:
                    researchers['David Richardson'] = {
                        'first_name': 'David', 'last_name': 'Richardson',
                        'institution': institution, 'state': current_state
                    }
                    researchers['Jane Richardson'] = {
                        'first_name': 'Jane', 'last_name': 'Richardson',
                        'institution': institution, 'state': current_state
                    }
                else:
                    # Split name into first and last
                    name_parts = full_name.split()
                    if len(name_parts) >= 2:
                        first_name = ' '.join(name_parts[:-1])
                        last_name = name_parts[-1]
                        
                        researchers[full_name] = {
                            'first_name': first_name,
                            'last_name': last_name,
                            'institution': institution,
                            'state': current_state
                        }
    
    print(f"Found {len(researchers)} researchers on website")
    return researchers, state_abbrevs

def update_database_locations():
    """Update all researchers with missing locations"""
    website_researchers, state_abbrevs = get_researchers_from_website()
    
    updated_count = 0
    matched_count = 0
    
    print("\nUpdating database...")
    
    for name, web_data in website_researchers.items():
        # Try to find matching researcher in database
        matches = Researcher.objects.filter(
            first_name__iexact=web_data['first_name'],
            last_name__iexact=web_data['last_name']
        )
        
        # If no exact match, try just last name
        if not matches.exists():
            matches = Researcher.objects.filter(
                last_name__iexact=web_data['last_name']
            )
        
        # Update researchers with missing/unknown location
        for researcher in matches:
            matched_count += 1
            
            # Check if location needs updating
            needs_update = (
                not researcher.state_province or 
                researcher.state_province.lower() in ['unknown', 'uk', 'unknow', ''] or
                not researcher.country or
                researcher.country.lower() in ['unknown', '']
            )
            
            if needs_update:
                # Set state (use abbreviation if available)
                state_value = state_abbrevs.get(web_data['state'], web_data['state'])
                country_value = 'USA' if web_data['state'] != 'Canada' else 'Canada'
                
                researcher.state_province = state_value
                researcher.country = country_value
                researcher.save()
                
                print(f"✓ Updated: {researcher.first_name} {researcher.last_name} -> {state_value}, {country_value}")
                updated_count += 1
            else:
                print(f"- Skipped: {researcher.first_name} {researcher.last_name} (already has location: {researcher.state_province})")
    
    print(f"\nSummary:")
    print(f"- Researchers found on website: {len(website_researchers)}")
    print(f"- Researchers matched in database: {matched_count}")
    print(f"- Researchers updated: {updated_count}")
    
    return updated_count

if __name__ == "__main__":
    try:
        updated_count = update_database_locations()
        print(f"\n🎉 SUCCESS: Updated {updated_count} researchers!")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()