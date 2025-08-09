"""
Bulk ORCID Lookup Script
Automatically searches and updates ORCID IDs for all researchers
"""

import requests
import time
from django.core.management.base import BaseCommand
from django.db import transaction
from home.models import Researcher
import json
from urllib.parse import quote


class Command(BaseCommand):
    help = 'Bulk lookup and update ORCID IDs for researchers'
    
    def __init__(self):
        super().__init__()
        self.api_base = 'https://pub.orcid.org/v3.0'
        self.found_count = 0
        self.not_found_count = 0
        self.error_count = 0
        self.already_has_orcid = 0
        
    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of researchers to process'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without saving changes'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Also check researchers who already have ORCID IDs'
        )
        
    def handle(self, *args, **options):
        limit = options.get('limit')
        dry_run = options.get('dry_run')
        verbose = options.get('verbose')
        update_existing = options.get('update_existing')
        
        self.stdout.write(self.style.SUCCESS('\n🔍 Starting ORCID Bulk Lookup'))
        self.stdout.write('=' * 60)
        
        # Get researchers
        researchers = Researcher.objects.filter(is_active=True)
        
        if not update_existing:
            from django.db.models import Q
            researchers = researchers.filter(
                Q(orcid_id__isnull=True) | Q(orcid_id='')
            )
            
        if limit:
            researchers = researchers[:limit]
            
        total = researchers.count()
        self.stdout.write(f'\n📊 Processing {total} researchers...\n')
        
        results = []
        
        for i, researcher in enumerate(researchers, 1):
            if researcher.orcid_id and researcher.orcid_id.strip() and not update_existing:
                self.already_has_orcid += 1
                continue
                
            # Progress indicator
            if i % 10 == 0:
                self.stdout.write(f'Progress: {i}/{total}...')
                
            # Search for ORCID
            orcid_data = self.search_orcid(researcher, verbose)
            
            if orcid_data:
                results.append({
                    'researcher': researcher,
                    'orcid': orcid_data['orcid'],
                    'confidence': orcid_data['confidence'],
                    'match_details': orcid_data['match_details']
                })
                
                if not dry_run and orcid_data['confidence'] >= 0.6:
                    researcher.orcid_id = orcid_data['orcid']
                    researcher.save(update_fields=['orcid_id'])
                    self.found_count += 1
                    
                    if verbose:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✅ {researcher.display_name}: {orcid_data["orcid"]} '
                                f'(confidence: {orcid_data["confidence"]:.2f})'
                            )
                        )
                elif orcid_data['confidence'] < 0.8:
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠️  {researcher.display_name}: Low confidence match '
                                f'({orcid_data["confidence"]:.2f})'
                            )
                        )
            else:
                self.not_found_count += 1
                if verbose:
                    self.stdout.write(f'❌ {researcher.display_name}: No ORCID found')
                    
            # Be nice to the API
            time.sleep(0.5)
            
        # Generate report
        self.generate_report(results, dry_run)
        
    def search_orcid(self, researcher, verbose=False):
        """Search ORCID API for a researcher"""
        try:
            # Build search query
            queries = []
            
            # Try different search strategies
            # Strategy 1: Full name + institution
            if researcher.institution:
                query1 = f'given-names:{researcher.first_name} AND family-name:{researcher.last_name} AND affiliation-org-name:"{researcher.institution}"'
                queries.append(query1)
            
            # Strategy 2: Just name
            query2 = f'given-names:{researcher.first_name} AND family-name:{researcher.last_name}'
            queries.append(query2)
            
            # Strategy 3: Email if available
            if researcher.institutional_email:
                query3 = f'email:{researcher.institutional_email}'
                queries.append(query3)
                
            for query in queries:
                url = f'https://pub.orcid.org/v3.0/search/?q={quote(query)}'
                
                headers = {
                    'Accept': 'application/json',
                    'User-Agent': 'APS PeptideLinks ORCID Matcher'
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('num-found', 0) > 0:
                        # Analyze results
                        best_match = self.analyze_matches(
                            researcher, 
                            data.get('result', [])
                        )
                        
                        if best_match:
                            return best_match
                            
        except Exception as e:
            self.error_count += 1
            if verbose:
                self.stdout.write(
                    self.style.ERROR(f'Error searching for {researcher.display_name}: {e}')
                )
                
        return None
        
    def analyze_matches(self, researcher, results):
        """Analyze ORCID search results and find best match"""
        if not results:
            return None
            
        best_match = None
        best_score = 0
        
        for result in results[:5]:  # Check top 5 results
            orcid_id = result.get('orcid-identifier', {}).get('path')
            if not orcid_id:
                continue
                
            # Calculate match score
            score = 0
            match_details = []
            
            # Get detailed record
            try:
                detail_url = f'{self.api_base}/{orcid_id}/person'
                headers = {'Accept': 'application/json'}
                detail_response = requests.get(detail_url, headers=headers, timeout=10)
                
                if detail_response.status_code == 200:
                    person_data = detail_response.json()
                    
                    # Check name match
                    given_names = person_data.get('name', {}).get('given-names', {}).get('value', '')
                    family_name = person_data.get('name', {}).get('family-name', {}).get('value', '')
                    
                    if given_names.lower() == researcher.first_name.lower():
                        score += 0.3
                        match_details.append('First name exact match')
                    elif researcher.first_name.lower() in given_names.lower():
                        score += 0.2
                        match_details.append('First name partial match')
                        
                    if family_name.lower() == researcher.last_name.lower():
                        score += 0.3
                        match_details.append('Last name exact match')
                    elif researcher.last_name.lower() in family_name.lower():
                        score += 0.2
                        match_details.append('Last name partial match')
                        
                    # Check affiliations
                    affiliations = person_data.get('affiliations', {}).get('affiliation', [])
                    for aff in affiliations:
                        org_name = aff.get('organization', {}).get('name', '')
                        if researcher.institution and researcher.institution.lower() in org_name.lower():
                            score += 0.4
                            match_details.append(f'Institution match: {org_name}')
                            break
                            
                    # Check keywords (research areas)
                    keywords = person_data.get('keywords', {}).get('keyword', [])
                    for kw in keywords:
                        kw_value = kw.get('value', '').lower()
                        if 'peptide' in kw_value or 'protein' in kw_value:
                            score += 0.1
                            match_details.append(f'Keyword match: {kw_value}')
                            
            except:
                pass
                
            if score > best_score:
                best_score = score
                best_match = {
                    'orcid': orcid_id,
                    'confidence': score,
                    'match_details': ', '.join(match_details)
                }
                
        return best_match
        
    def generate_report(self, results, dry_run):
        """Generate a detailed report of the ORCID lookup results"""
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📊 ORCID LOOKUP REPORT'))
        self.stdout.write('=' * 60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN - No changes saved\n'))
            
        self.stdout.write(f'\n✅ Found with high confidence: {self.found_count}')
        self.stdout.write(f'❌ Not found: {self.not_found_count}')
        self.stdout.write(f'⚠️  Errors: {self.error_count}')
        self.stdout.write(f'📌 Already had ORCID: {self.already_has_orcid}')
        
        # High confidence matches
        high_confidence = [r for r in results if r['confidence'] >= 0.8]
        if high_confidence:
            self.stdout.write(f'\n\n🎯 HIGH CONFIDENCE MATCHES ({len(high_confidence)}):')
            self.stdout.write('-' * 40)
            for r in high_confidence[:20]:  # Show first 20
                self.stdout.write(
                    f"{r['researcher'].display_name}\n"
                    f"  → {r['orcid']} (confidence: {r['confidence']:.2f})\n"
                    f"  → {r['match_details']}\n"
                )
                
        # Low confidence matches that need review
        low_confidence = [r for r in results if 0.4 <= r['confidence'] < 0.8]
        if low_confidence:
            self.stdout.write(f'\n\n⚠️  LOW CONFIDENCE - NEED REVIEW ({len(low_confidence)}):')
            self.stdout.write('-' * 40)
            for r in low_confidence[:20]:
                self.stdout.write(
                    f"{r['researcher'].display_name}\n"
                    f"  → {r['orcid']} (confidence: {r['confidence']:.2f})\n"
                    f"  → {r['match_details']}\n"
                )
                
        # Save detailed results to file
        report_file = '/tmp/orcid_lookup_results.json'
        with open(report_file, 'w') as f:
            json.dump([{
                'name': r['researcher'].display_name,
                'institution': r['researcher'].institution,
                'orcid': r['orcid'],
                'confidence': r['confidence'],
                'match_details': r['match_details']
            } for r in results], f, indent=2)
            
        self.stdout.write(f'\n\n📄 Detailed results saved to: {report_file}')
        self.stdout.write('\n' + '=' * 60)
        
        # Suggestions for improvement
        self.stdout.write(self.style.SUCCESS('\n💡 SUGGESTIONS:'))
        self.stdout.write('1. Review low-confidence matches manually')
        self.stdout.write('2. Add email addresses to improve matching')
        self.stdout.write('3. Run with --update-existing to recheck existing ORCIDs')
        self.stdout.write('4. Use --dry-run first to preview results\n')