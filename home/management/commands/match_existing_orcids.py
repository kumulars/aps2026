"""
Enhanced ORCID matching for existing PeptideLinks researchers
"""

import requests
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from home.models import Researcher
import re


class Command(BaseCommand):
    help = 'Match existing PeptideLinks researchers with their ORCID profiles'
    
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'APS-PeptideLinks/1.0'
        })

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-researchers',
            type=int,
            default=20,
            help='Maximum number of researchers to process',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show matches without updating database',
        )

    def handle(self, *args, **options):
        self.stdout.write("🔍 Enhanced ORCID matching for existing researchers...")
        
        # Get researchers without ORCID IDs
        researchers = Researcher.objects.filter(
            is_active=True,
            orcid_id__isnull=True
        ).exclude(orcid_id='').order_by('last_name')[:options['max_researchers']]
        
        matches_found = 0
        
        for researcher in researchers:
            self.stdout.write(f"🔍 Searching: {researcher.display_name}")
            
            orcid_id = self.find_orcid_for_researcher(researcher)
            
            if orcid_id:
                if options['dry_run']:
                    self.stdout.write(f"✅ [DRY RUN] Would add ORCID {orcid_id} to {researcher.display_name}")
                else:
                    researcher.orcid_id = orcid_id
                    researcher.save(update_fields=['orcid_id'])
                    self.stdout.write(f"✅ Added ORCID {orcid_id} to {researcher.display_name}")
                
                matches_found += 1
            else:
                self.stdout.write(f"❌ No ORCID found for {researcher.display_name}")
                
            time.sleep(1)  # Rate limiting
            
        self.stdout.write(f"\\n🎯 Found {matches_found} ORCID matches!")

    def find_orcid_for_researcher(self, researcher):
        """Find ORCID ID for a specific researcher"""
        try:
            # Search by name
            search_queries = [
                f'given-names:"{researcher.first_name}" AND family-name:"{researcher.last_name}"',
                f'"{researcher.first_name} {researcher.last_name}"',
            ]
            
            for query in search_queries:
                orcid_id = self.search_orcid_by_query(query, researcher)
                if orcid_id:
                    return orcid_id
                    
        except Exception as e:
            self.stdout.write(f"❌ Error searching for {researcher.display_name}: {e}")
            
        return None

    def search_orcid_by_query(self, query, researcher):
        """Search ORCID with a specific query"""
        try:
            url = 'https://pub.orcid.org/v3.0/search'
            params = {'q': query, 'rows': 10}
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            results = response.json().get('result', [])
            
            for result in results:
                orcid_id = result.get('orcid-identifier', {}).get('path', '')
                if orcid_id:
                    # Get detailed profile to check institution
                    if self.validate_orcid_match(orcid_id, researcher):
                        return orcid_id
                        
        except Exception as e:
            pass
            
        return None

    def validate_orcid_match(self, orcid_id, researcher):
        """Validate that ORCID profile matches our researcher"""
        try:
            url = f'https://pub.orcid.org/v3.0/{orcid_id}'
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                return False
                
            profile = response.json()
            
            # Check name match
            person = profile.get('person', {})
            name = person.get('name', {})
            
            orcid_given = name.get('given-names', {}).get('value', '') if name.get('given-names') else ''
            orcid_family = name.get('family-name', {}).get('value', '') if name.get('family-name') else ''
            
            # Flexible name matching
            if not self.names_match_flexible(researcher.first_name, researcher.last_name, orcid_given, orcid_family):
                return False
                
            # Check institution (more flexible)
            if researcher.institution and self.institution_matches(profile, researcher.institution):
                return True
                
            # If institution doesn't match but names do, still consider it (some researchers move)
            self.stdout.write(f"  🤔 Name match for {orcid_id} but institution unclear")
            return True
            
        except Exception as e:
            return False

    def names_match_flexible(self, our_first, our_last, orcid_first, orcid_last):
        """Flexible name matching"""
        # Normalize names
        our_first = self.normalize_name(our_first)
        our_last = self.normalize_name(our_last)
        orcid_first = self.normalize_name(orcid_first)
        orcid_last = self.normalize_name(orcid_last)
        
        # Check if last names match (most important)
        if our_last.lower() != orcid_last.lower():
            return False
            
        # Check first names (more flexible)
        if our_first.lower() == orcid_first.lower():
            return True
            
        # Check if one is contained in the other (handles middle names)
        if our_first.lower() in orcid_first.lower() or orcid_first.lower() in our_first.lower():
            return True
            
        # Check first initials
        if our_first[0].lower() == orcid_first[0].lower():
            return True
            
        return False

    def normalize_name(self, name):
        """Normalize name for comparison"""
        if not name:
            return ''
        # Remove extra spaces, hyphens, etc.
        return re.sub(r'[\\s\\-\\.]+', ' ', name).strip()

    def institution_matches(self, profile, our_institution):
        """Check if ORCID profile institution matches ours"""
        try:
            activities = profile.get('activities-summary', {})
            employments = activities.get('employments', {}).get('employment-summary', [])
            
            our_inst_lower = our_institution.lower()
            
            for employment in employments:
                org = employment.get('organization', {})
                org_name = org.get('name', '').lower()
                
                if org_name:
                    # Direct match
                    if org_name in our_inst_lower or our_inst_lower in org_name:
                        return True
                        
                    # Check for common abbreviations
                    if self.institutions_similar(org_name, our_inst_lower):
                        return True
                        
        except Exception as e:
            pass
            
        return False

    def institutions_similar(self, orcid_inst, our_inst):
        """Check if institutions are similar"""
        # Common patterns
        patterns = [
            (r'university', r'univ'),
            (r'institute', r'inst'),
            (r'college', r'coll'),
            (r'&', r'and'),
        ]
        
        for pattern in patterns:
            orcid_inst = re.sub(pattern[0], pattern[1], orcid_inst)
            our_inst = re.sub(pattern[0], pattern[1], our_inst)
            
        # Check if key words match
        orcid_words = set(re.findall(r'\\b\\w{4,}\\b', orcid_inst))
        our_words = set(re.findall(r'\\b\\w{4,}\\b', our_inst))
        
        # If they share significant words, consider them similar
        common_words = orcid_words.intersection(our_words)
        return len(common_words) >= 1