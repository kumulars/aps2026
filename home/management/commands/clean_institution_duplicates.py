"""
Clean Institution Duplicates Script
Safely removes duplicate institution names while preserving database relationships
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from home.models import Researcher
import re


class Command(BaseCommand):
    help = 'Clean duplicate institution names and standardize format'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without saving'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )
        
    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        verbose = options.get('verbose')
        
        self.stdout.write(self.style.SUCCESS('\n🧹 Institution Duplicate Cleaner'))
        self.stdout.write('=' * 60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved\n'))
            
        # Track changes
        changes = {
            'repeated_institution': [],
            'repeated_keywords': [],
            'extra_spaces': [],
            'country_format': [],
            'standardized_abbrev': []
        }
        
        researchers = Researcher.objects.filter(is_active=True)
        total = researchers.count()
        
        self.stdout.write(f'Checking {total} researchers...\n')
        
        with transaction.atomic():
            for i, researcher in enumerate(researchers, 1):
                if i % 100 == 0:
                    self.stdout.write(f'Progress: {i}/{total}...')
                    
                original = researcher.institution or ''
                cleaned = original
                change_made = False
                change_types = []
                
                # 1. Remove exact duplicates (e.g., "University of Georgia University of Georgia")
                cleaned, changed = self.remove_exact_duplicates(cleaned)
                if changed:
                    change_made = True
                    change_types.append('repeated_institution')
                
                # 2. Remove repeated keywords
                cleaned, changed = self.remove_repeated_keywords(cleaned)
                if changed:
                    change_made = True
                    change_types.append('repeated_keywords')
                
                # 3. Clean extra spaces
                cleaned, changed = self.clean_extra_spaces(cleaned)
                if changed:
                    change_made = True
                    change_types.append('extra_spaces')
                
                # 4. Standardize country format (optional - keep or remove country suffix)
                # For now, we'll keep countries but ensure proper format
                cleaned, changed = self.standardize_country_format(cleaned)
                if changed:
                    change_made = True
                    change_types.append('country_format')
                
                # 5. Standardize common abbreviations
                cleaned, changed = self.standardize_abbreviations(cleaned)
                if changed:
                    change_made = True
                    change_types.append('standardized_abbrev')
                
                # Save changes if needed
                if change_made and cleaned != original:
                    for change_type in change_types:
                        changes[change_type].append({
                            'researcher': researcher,
                            'original': original,
                            'cleaned': cleaned
                        })
                    
                    if not dry_run:
                        researcher.institution = cleaned
                        researcher.save(update_fields=['institution'])
                    
                    if verbose:
                        self.stdout.write(
                            f'  {researcher.display_name}\n'
                            f'    From: "{original}"\n'
                            f'    To:   "{cleaned}"\n'
                        )
            
            if dry_run:
                transaction.set_rollback(True)
        
        # Report results
        self.print_report(changes, dry_run)
        
    def remove_exact_duplicates(self, text):
        """Remove exact institution name duplicates"""
        if not text:
            return text, False
            
        # Check if the institution name is repeated exactly
        words = text.split()
        if len(words) >= 4:  # Need at least 4 words to have a duplicate
            # Check various split points
            for split_point in range(2, len(words) - 1):
                first_part = ' '.join(words[:split_point])
                remaining = ' '.join(words[split_point:])
                
                # Check if first part appears in remaining
                if first_part == remaining:
                    return first_part, True
                    
                # Check if first part is at the start of remaining
                if remaining.startswith(first_part + ' '):
                    # Remove the duplicate
                    cleaned = first_part + remaining[len(first_part):].strip()
                    return cleaned, True
                    
        return text, False
        
    def remove_repeated_keywords(self, text):
        """Remove repeated keywords like University, College, Institute"""
        if not text:
            return text, False
            
        changed = False
        original = text
        
        # Keywords to check for repetition
        keywords = ['University', 'College', 'Institute', 'School', 'Department', 'Center']
        
        for keyword in keywords:
            count = text.count(keyword)
            if count > 1:
                # Keep only the first occurrence in proper context
                # This is tricky - we want "University of Georgia" not "of Georgia University"
                parts = text.split(keyword)
                
                # Reconstruct keeping logical structure
                if len(parts) > 2:
                    # Multiple occurrences - need smart handling
                    # For now, keep first occurrence and clean up
                    first_occurrence_end = text.index(keyword) + len(keyword)
                    before = text[:first_occurrence_end]
                    after = text[first_occurrence_end:]
                    
                    # Remove keyword from after if it appears again immediately
                    after = after.replace(keyword + ' ' + keyword, '')
                    after = after.replace(' ' + keyword + ' of', ' of')
                    after = after.replace(' ' + keyword, '', 1)  # Remove first occurrence in after
                    
                    text = before + after
                    changed = True
                    
        # Clean up any double spaces created
        text = ' '.join(text.split())
        
        return text, (text != original)
        
    def clean_extra_spaces(self, text):
        """Remove extra spaces and clean whitespace"""
        if not text:
            return text, False
            
        original = text
        # Remove extra spaces
        text = ' '.join(text.split())
        # Remove spaces before punctuation
        text = re.sub(r'\s+([,\.\)\]])', r'\1', text)
        # Remove spaces after opening brackets
        text = re.sub(r'([\(\[])\s+', r'\1', text)
        
        return text, (text != original)
        
    def standardize_country_format(self, text):
        """Standardize country names in institution field"""
        if not text:
            return text, False
            
        original = text
        
        # Common country patterns at the end of institution names
        country_mappings = {
            'USA': 'USA',
            'U.S.A.': 'USA',
            'U.S.': 'USA',
            'United States': 'USA',
            'UK': 'UK',
            'U.K.': 'UK',
            'United Kingdom': 'UK',
        }
        
        # Check if country is already properly formatted with comma
        if re.search(r',\s+[A-Z]{2,}$', text):
            # Already has format like "University, COUNTRY"
            return text, False
            
        # Check for country at end without comma
        for long_form, short_form in country_mappings.items():
            if text.endswith(' ' + long_form):
                # Remove and re-add with comma
                base = text[:-len(long_form)].strip()
                text = f"{base}, {short_form}"
                return text, True
                
        return text, (text != original)
        
    def standardize_abbreviations(self, text):
        """Standardize common university abbreviations"""
        if not text:
            return text, False
            
        original = text
        
        # Common abbreviations to expand
        abbreviations = {
            r'^U\s+': 'University of ',
            r'^UC\s+': 'University of California ',
            r'^SUNY\s+': 'State University of New York ',
            r'^CUNY\s+': 'City University of New York ',
            r'\s+U$': ' University',
            r'\s+Univ$': ' University',
            r'\s+Univ\s+': ' University ',
        }
        
        for pattern, replacement in abbreviations.items():
            text = re.sub(pattern, replacement, text)
            
        return text, (text != original)
        
    def print_report(self, changes, dry_run):
        """Print a summary report of changes"""
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('📊 CLEANING REPORT'))
        self.stdout.write('=' * 60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN - No changes were saved\n'))
            
        total_changes = sum(len(v) for v in changes.values())
        
        self.stdout.write(f'\n📈 Total changes: {total_changes}')
        
        for change_type, items in changes.items():
            if items:
                self.stdout.write(f'\n{change_type.replace("_", " ").title()}: {len(items)}')
                # Show first 3 examples
                for item in items[:3]:
                    self.stdout.write(f'  • {item["researcher"].display_name}')
                    self.stdout.write(f'    From: "{item["original"]}"')
                    self.stdout.write(f'    To:   "{item["cleaned"]}"')
                    
        if not dry_run and total_changes > 0:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Successfully cleaned {total_changes} institution names!'))
        elif total_changes == 0:
            self.stdout.write(self.style.SUCCESS('\n✅ No duplicates found - institutions are clean!'))