"""
Management command to automatically tag researchers with research areas.
Analyzes researcher websites to extract keywords and assign matching research areas.
"""
from django.core.management.base import BaseCommand
from home.models import Researcher, ResearchArea
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urljoin, urlparse


class Command(BaseCommand):
    help = 'Automatically tag researchers with research areas based on website analysis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be tagged without making changes',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=50,
            help='Limit number of researchers to process (default: 50)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        
        # Get research areas and create keyword mapping
        research_areas = {area.name: area for area in ResearchArea.objects.all()}
        
        # Define keyword patterns for each research area
        keyword_patterns = {
            'Antimicrobial Peptides': [
                'antimicrobial peptide', 'antibacterial peptide', 'antifungal peptide',
                'antibiotic peptide', 'antimicrobial', 'antibacterial', 'antifungal',
                'host defense peptide', 'defensin', 'cathelicidin', 'bacteriocin'
            ],
            'Bioorganic Chemistry': [
                'bioorganic chemistry', 'bioorganic', 'organic synthesis', 'medicinal chemistry',
                'chemical biology', 'synthetic biology', 'organic chemistry', 'synthesis'
            ],
            'Chemical Biology': [
                'chemical biology', 'chemical probe', 'small molecule', 'drug design',
                'chemical tool', 'bioactive compound', 'chemical genetics'
            ],
            'Computational Chemistry': [
                'computational chemistry', 'molecular dynamics', 'quantum chemistry',
                'molecular modeling', 'computational', 'simulation', 'docking',
                'QSAR', 'molecular mechanics', 'ab initio', 'DFT'
            ],
            'Drug Discovery': [
                'drug discovery', 'drug development', 'pharmaceutical', 'therapeutics',
                'drug design', 'lead optimization', 'clinical trial', 'pharma'
            ],
            'Materials Science': [
                'materials science', 'biomaterials', 'nanomaterials', 'hydrogel',
                'scaffold', 'polymer', 'nanoparticle', 'materials', 'nanotechnology'
            ],
            'Medicinal Chemistry': [
                'medicinal chemistry', 'drug design', 'SAR', 'structure-activity',
                'pharmaceutical chemistry', 'medicinal', 'therapeutic'
            ],
            'Peptide Synthesis': [
                'peptide synthesis', 'solid phase synthesis', 'SPPS', 'peptide chemistry',
                'synthesis', 'coupling', 'protection', 'deprotection', 'synthetic peptide'
            ],
            'Protein Engineering': [
                'protein engineering', 'protein design', 'directed evolution',
                'mutagenesis', 'protein modification', 'enzyme engineering',
                'protein structure', 'fold', 'engineering'
            ],
            'Structural Biology': [
                'structural biology', 'crystal structure', 'NMR', 'X-ray crystallography',
                'protein structure', 'structure', 'crystallography', 'structural'
            ]
        }
        
        # Get researchers with websites who haven't been tagged yet
        researchers = Researcher.objects.filter(
            is_active=True,
            research_areas__isnull=True
        ).exclude(
            website_url__isnull=True
        ).exclude(
            website_url=''
        )[:limit]
        
        self.stdout.write(f"Processing {researchers.count()} researchers...")
        
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        # Handle SSL issues gracefully
        session.verify = False
        requests.packages.urllib3.disable_warnings()
        
        processed = 0
        tagged = 0
        
        for researcher in researchers:
            processed += 1
            self.stdout.write(f"\n[{processed}/{researchers.count()}] Processing {researcher.first_name} {researcher.last_name}")
            
            try:
                # Fetch the webpage
                response = session.get(researcher.website_url, timeout=10)
                response.raise_for_status()
                
                # Parse content
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract text content
                text_content = soup.get_text().lower()
                
                # Find matching research areas
                matches = []
                for area_name, keywords in keyword_patterns.items():
                    for keyword in keywords:
                        if keyword.lower() in text_content:
                            matches.append(area_name)
                            break  # Found one match for this area, move to next area
                
                if matches:
                    self.stdout.write(f"  Found matches: {', '.join(matches)}")
                    
                    if not dry_run:
                        # Add research areas to the researcher
                        for area_name in matches:
                            if area_name in research_areas:
                                researcher.research_areas.add(research_areas[area_name])
                        researcher.save()
                    
                    tagged += 1
                else:
                    self.stdout.write("  No matches found")
                
                # Be polite to servers
                time.sleep(1)
                
            except requests.RequestException as e:
                self.stdout.write(f"  Error fetching {researcher.website_url}: {e}")
                continue
            except Exception as e:
                self.stdout.write(f"  Error processing {researcher.first_name} {researcher.last_name}: {e}")
                continue
        
        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary {'(DRY RUN)' if dry_run else ''}:\n"
                f"  Researchers processed: {processed}\n"
                f"  Researchers tagged: {tagged}\n"
                f"  Success rate: {(tagged/processed*100):.1f}%" if processed > 0 else "  Success rate: 0%"
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nThis was a dry run. Use without --dry-run to make changes."
                )
            )