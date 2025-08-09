"""
ORCID API integration for enhanced researcher data
"""

import requests
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from home.models import Researcher, ResearchArea
import re
from datetime import datetime, timedelta


class Command(BaseCommand):
    help = 'Sync researcher data with ORCID API'
    
    def __init__(self):
        super().__init__()
        self.orcid_base_url = 'https://pub.orcid.org/v3.0'
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'APS-PeptideLinks/1.0 (https://www.americanpeptidesociety.org)'
        })

    def add_arguments(self, parser):
        parser.add_argument(
            '--search-peptides',
            action='store_true',
            help='Search ORCID for peptide researchers',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true', 
            help='Update existing researchers with ORCID data',
        )
        parser.add_argument(
            '--max-results',
            type=int,
            default=100,
            help='Maximum number of ORCID profiles to process',
        )

    def handle(self, *args, **options):
        self.stdout.write("🔬 Starting ORCID integration...")
        
        if options['search_peptides']:
            self.search_peptide_researchers(options['max_results'])
            
        if options['update_existing']:
            self.update_existing_researchers()

    def search_peptide_researchers(self, max_results):
        """Search ORCID for peptide science researchers"""
        self.stdout.write("🔍 Searching ORCID for peptide researchers...")
        
        # Peptide-related search terms
        search_terms = [
            'peptide synthesis',
            'peptide chemistry', 
            'bioactive peptides',
            'protein peptide',
            'peptide drug',
            'cyclic peptides',
            'antimicrobial peptides',
            'peptide therapeutics',
        ]
        
        found_researchers = []
        
        for term in search_terms:
            self.stdout.write(f"🔍 Searching for: {term}")
            results = self.search_orcid_by_keywords(term, max_results // len(search_terms))
            found_researchers.extend(results)
            time.sleep(1)  # Rate limiting
            
        # Remove duplicates
        unique_orcids = {}
        for researcher in found_researchers:
            orcid_id = researcher.get('orcid-identifier', {}).get('path')
            if orcid_id and orcid_id not in unique_orcids:
                unique_orcids[orcid_id] = researcher
                
        self.stdout.write(f"✅ Found {len(unique_orcids)} unique peptide researchers")
        
        # Process each researcher
        added_count = 0
        for orcid_id, basic_info in unique_orcids.items():
            detailed_info = self.get_orcid_profile(orcid_id)
            if detailed_info and self.is_relevant_researcher(detailed_info):
                if self.add_orcid_researcher(detailed_info):
                    added_count += 1
                time.sleep(0.5)  # Rate limiting
                
        self.stdout.write(f"✅ Added {added_count} new researchers from ORCID")

    def search_orcid_by_keywords(self, keywords, max_results):
        """Search ORCID by keywords"""
        try:
            url = f"{self.orcid_base_url}/search"
            params = {
                'q': f'keyword:"{keywords}"',
                'rows': min(max_results, 200),  # ORCID limit
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get('result', [])
            
        except requests.RequestException as e:
            self.stdout.write(f"❌ ORCID search failed: {e}")
            return []

    def get_orcid_profile(self, orcid_id):
        """Get detailed ORCID profile"""
        try:
            url = f"{self.orcid_base_url}/{orcid_id}"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            self.stdout.write(f"❌ Failed to get ORCID profile {orcid_id}: {e}")
            return None

    def is_relevant_researcher(self, profile):
        """Check if ORCID profile is relevant to peptide science"""
        # Check keywords, research areas, publications
        keywords = self.extract_keywords(profile)
        
        peptide_keywords = [
            'peptide', 'protein', 'amino acid', 'bioactive',
            'synthesis', 'medicinal chemistry', 'drug discovery',
            'biochemistry', 'molecular biology', 'therapeutics'
        ]
        
        keyword_text = ' '.join(keywords).lower()
        return any(keyword in keyword_text for keyword in peptide_keywords)

    def extract_keywords(self, profile):
        """Extract keywords from ORCID profile"""
        keywords = []
        
        # Extract from keywords section
        try:
            keyword_section = profile.get('person', {}).get('keywords', {})
            if keyword_section and 'keyword' in keyword_section:
                for kw in keyword_section['keyword']:
                    if isinstance(kw, dict) and 'content' in kw:
                        keywords.append(kw['content'])
        except:
            pass
            
        # Extract from research areas/subjects
        try:
            research_section = profile.get('person', {}).get('researcher-urls', {})
            if research_section:
                # Process research URLs and descriptions
                pass
        except:
            pass
            
        return keywords

    def add_orcid_researcher(self, profile):
        """Add researcher from ORCID profile"""
        try:
            # Extract basic info
            person_info = profile.get('person', {})
            name_info = person_info.get('name', {})
            
            given_names = name_info.get('given-names', {}).get('value', '') if name_info.get('given-names') else ''
            family_name = name_info.get('family-name', {}).get('value', '') if name_info.get('family-name') else ''
            
            if not given_names or not family_name:
                return False
                
            # Extract employment info
            employment = self.extract_employment(profile)
            institution = employment.get('organization', '') if employment else ''
            
            # Extract ORCID ID
            orcid_id = profile.get('orcid-identifier', {}).get('path', '')
            
            # Check if already exists
            existing = Researcher.objects.filter(
                first_name=given_names,
                last_name=family_name,
                institution=institution
            ).first()
            
            if existing:
                # Update with ORCID info
                if not existing.orcid_id and orcid_id:
                    existing.orcid_id = orcid_id
                    existing.save(update_fields=['orcid_id'])
                return False
                
            # Create new researcher
            researcher = Researcher.objects.create(
                first_name=given_names,
                last_name=family_name,
                institution=institution,
                orcid_id=orcid_id,
                country=employment.get('country', 'USA') if employment else 'USA',
                city=employment.get('city', '') if employment else '',
                is_active=True,
                is_verified=False,  # Needs manual verification
                last_verified=timezone.now(),
            )
            
            self.stdout.write(f"➕ Added from ORCID: {given_names} {family_name}")
            return True
            
        except Exception as e:
            self.stdout.write(f"❌ Error adding ORCID researcher: {e}")
            return False

    def extract_employment(self, profile):
        """Extract current employment from ORCID profile"""
        try:
            activities = profile.get('activities-summary', {})
            employments = activities.get('employments', {}).get('employment-summary', [])
            
            if not employments:
                return None
                
            # Find most recent employment
            current_employment = None
            for emp in employments:
                end_date = emp.get('end-date')
                if not end_date:  # Current position
                    current_employment = emp
                    break
                    
            if not current_employment and employments:
                current_employment = employments[0]  # Most recent
                
            if current_employment:
                org = current_employment.get('organization', {})
                address = org.get('address', {})
                
                return {
                    'organization': org.get('name', ''),
                    'department': current_employment.get('department-name', ''),
                    'city': address.get('city', ''),
                    'country': address.get('country', ''),
                }
                
        except Exception as e:
            self.stdout.write(f"❌ Error extracting employment: {e}")
            
        return None

    def update_existing_researchers(self):
        """Update existing researchers with ORCID data"""
        self.stdout.write("🔄 Updating existing researchers with ORCID data...")
        
        # Find researchers without ORCID IDs
        researchers_without_orcid = Researcher.objects.filter(
            orcid_id__isnull=True,
            is_active=True
        ).exclude(orcid_id='')
        
        updated_count = 0
        
        for researcher in researchers_without_orcid[:50]:  # Limit for now
            self.stdout.write(f"🔍 Searching ORCID for: {researcher.display_name}")
            
            # Search for this researcher
            search_query = f'given-names:"{researcher.first_name}" AND family-name:"{researcher.last_name}"'
            
            try:
                url = f"{self.orcid_base_url}/search"
                params = {
                    'q': search_query,
                    'rows': 10,
                }
                
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()
                
                results = response.json().get('result', [])
                
                # Check each result for institution match
                for result in results:
                    orcid_id = result.get('orcid-identifier', {}).get('path', '')
                    if orcid_id:
                        profile = self.get_orcid_profile(orcid_id)
                        if profile and self.matches_researcher(profile, researcher):
                            researcher.orcid_id = orcid_id
                            researcher.save(update_fields=['orcid_id'])
                            updated_count += 1
                            self.stdout.write(f"✅ Found ORCID for: {researcher.display_name}")
                            break
                            
                time.sleep(1)  # Rate limiting
                
            except requests.RequestException as e:
                self.stdout.write(f"❌ Search failed for {researcher.display_name}: {e}")
                
        self.stdout.write(f"✅ Updated {updated_count} researchers with ORCID IDs")

    def matches_researcher(self, profile, researcher):
        """Check if ORCID profile matches our researcher"""
        try:
            employment = self.extract_employment(profile)
            if not employment:
                return False
                
            # Check institution similarity
            orcid_institution = employment.get('organization', '').lower()
            our_institution = researcher.institution.lower()
            
            # Simple similarity check
            if orcid_institution in our_institution or our_institution in orcid_institution:
                return True
                
            # Check for common institution name variations
            institution_keywords = re.findall(r'\b\w+\b', our_institution)
            for keyword in institution_keywords:
                if len(keyword) > 4 and keyword in orcid_institution:
                    return True
                    
        except Exception as e:
            pass
            
        return False