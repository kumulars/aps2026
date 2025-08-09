"""
Management command to fix researcher country assignments.
Identifies international researchers miscategorized as USA and updates their country field.
"""
from django.core.management.base import BaseCommand
from home.models import Researcher
import re


class Command(BaseCommand):
    help = 'Fix researcher country assignments based on institution data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made"))
        
        # Define country patterns to look for in institution field
        country_patterns = {
            'UK': [r'\bUK\b', r'United Kingdom', r'England', r'Scotland', r'Wales', 
                   r'Cambridge', r'Oxford', r'London', r'Manchester', r'Edinburgh'],
            'Japan': [r'\bJAPAN\b', r'Tokyo', r'Kyoto', r'Osaka', r'Nagoya', r'Hokkaido'],
            'Germany': [r'\bGERMANY\b', r'Max Planck', r'Göttingen', r'München', r'Berlin', 
                       r'Tübingen', r'Heidelberg', r'TÃ¼bingen'],
            'France': [r'\bFRANCE\b', r'CNRS', r'Université', r'Strasbourg', r'Paris', r'Lyon'],
            'Netherlands': [r'\bNETHERLANDS\b', r'Amsterdam', r'Utrecht', r'Groningen', r'Leiden'],
            'Switzerland': [r'\bSWITZERLAND\b', r'\bETH\b', r'Zurich', r'Zürich', r'Geneva', r'Basel'],
            'Canada': [r'\bCANADA\b', r'McGill', r'Toronto', r'UBC', r'Alberta', r'Montreal'],
            'Australia': [r'\bAUSTRALIA\b', r'Sydney', r'Melbourne', r'Brisbane', r'Perth'],
            'China': [r'\bCHINA\b', r'Chinese Academy', r'Beijing', r'Shanghai', r'Tsinghua'],
            'South Korea': [r'\bKOREA\b', r'Seoul', r'KAIST', r'Yonsei'],
            'Singapore': [r'\bSINGAPORE\b', r'NUS', r'Nanyang'],
            'Israel': [r'\bISRAEL\b', r'Weizmann', r'Hebrew University', r'Tel Aviv'],
            'Italy': [r'\bITALY\b', r'Milano', r'Roma', r'Napoli', r'Firenze'],
            'Spain': [r'\bSPAIN\b', r'Barcelona', r'Madrid', r'Valencia', r'Compostela'],
            'Sweden': [r'\bSWEDEN\b', r'Stockholm', r'Uppsala', r'Lund', r'Karolinska'],
            'Denmark': [r'\bDENMARK\b', r'Copenhagen', r'Aarhus'],
            'Belgium': [r'\bBELGIUM\b', r'Brussels', r'Leuven', r'Ghent'],
            'Austria': [r'\bAUSTRIA\b', r'Vienna', r'Innsbruck', r'Graz'],
            'Chile': [r'\bCHILE\b', r'Universidad de Chile', r'Santiago'],
            'Brazil': [r'\bBRAZIL\b', r'São Paulo', r'Rio de Janeiro'],
            'India': [r'\bINDIA\b', r'IIT', r'Mumbai', r'Delhi', r'Bangalore'],
            'New Zealand': [r'NEW ZEALAND', r'Auckland', r'Wellington', r'Canterbury'],
            'Norway': [r'\bNORWAY\b', r'Oslo', r'Bergen', r'Trondheim'],
            'Finland': [r'\bFINLAND\b', r'Helsinki', r'Turku'],
            'Poland': [r'\bPOLAND\b', r'Warsaw', r'Krakow', r'Wroclaw'],
            'Czech Republic': [r'CZECH', r'Prague', r'Brno'],
            'Portugal': [r'\bPORTUGAL\b', r'Lisbon', r'Porto', r'Coimbra'],
            'Greece': [r'\bGREECE\b', r'Athens', r'Thessaloniki'],
            'Russia': [r'\bRUSSIA\b', r'Moscow', r'Petersburg'],
            'South Africa': [r'SOUTH AFRICA', r'Cape Town', r'Johannesburg'],
            'Mexico': [r'\bMEXICO\b', r'UNAM', r'Mexico City'],
            'Argentina': [r'\bARGENTINA\b', r'Buenos Aires'],
        }
        
        # US state abbreviations to protect from false positives
        us_states = {
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        }
        
        # Get all researchers currently marked as USA
        researchers = Researcher.objects.filter(country='USA')
        self.stdout.write(f"Checking {researchers.count()} researchers currently marked as USA...")
        
        updates = []
        protected = []
        
        for researcher in researchers:
            institution = researcher.institution or ''
            
            # Check if this researcher has a US state - if so, keep as USA
            if researcher.state_province in us_states:
                continue
            
            # Check for explicit USA markers
            if any(marker in institution.upper() for marker in ['USA', 'U.S.A.', 'UNITED STATES']):
                protected.append(researcher)
                continue
            
            # Check against international patterns
            detected_country = None
            for country, patterns in country_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, institution, re.IGNORECASE):
                        detected_country = country
                        break
                if detected_country:
                    break
            
            if detected_country:
                updates.append((researcher, detected_country))
                
                if dry_run:
                    self.stdout.write(
                        f"Would update: {researcher.last_name}, {researcher.first_name} "
                        f"({institution}) -> {detected_country}"
                    )
                else:
                    researcher.country = detected_country
                    researcher.state_province = ''  # Clear state for international
                    researcher.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Updated: {researcher.last_name}, {researcher.first_name} "
                            f"({institution}) -> {detected_country}"
                        )
                    )
        
        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.SUCCESS(
                f"Summary {'(DRY RUN)' if dry_run else ''}:\n"
                f"  Total researchers checked: {researchers.count()}\n"
                f"  International researchers found: {len(updates)}\n"
                f"  USA researchers preserved: {researchers.count() - len(updates)}\n"
                f"  Explicitly protected (had USA in institution): {len(protected)}"
            )
        )
        
        if updates and not dry_run:
            # Show country distribution
            self.stdout.write("\nNew country distribution:")
            country_counts = {}
            for _, country in updates:
                country_counts[country] = country_counts.get(country, 0) + 1
            
            for country, count in sorted(country_counts.items()):
                self.stdout.write(f"  {country}: {count} researchers")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nThis was a dry run. Use without --dry-run to make changes."
                )
            )