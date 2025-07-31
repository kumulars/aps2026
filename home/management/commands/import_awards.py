"""
Import awards data from CSV file into the database.

This command imports award recipients from a cleaned CSV export, creating
award types as needed and handling data validation, deduplication, and
error recovery.
"""

import csv
import logging
import os
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError
from django.utils.text import slugify
from django.utils import timezone
from django.core.exceptions import ValidationError

from home.models import AwardType, AwardRecipient

# Configure logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to import award recipients from CSV file."""
    
    help = 'Import award recipients from CSV file'
    
    # Award type mappings (normalize variations)
    AWARD_TYPE_MAPPINGS = {
        'merrifield': {
            'slug': 'merrifield',
            'name': 'R. Bruce Merrifield Award',
            'description': 'The Merrifield Award recognizes outstanding contributions to peptide science.',
            'established_year': 1977,
            'display_order': 1
        },
        'merrifeild': 'merrifield',  # Typo correction
        'duvigneaud': {
            'slug': 'duvigneaud',
            'name': 'Vincent du Vigneaud Award',
            'description': 'The Vincent du Vigneaud Award recognizes outstanding achievements in peptide research.',
            'established_year': 1984,
            'display_order': 2
        },
        'hirschmann': {
            'slug': 'hirschmann',
            'name': 'Ralph F. Hirschmann Award in Peptide Chemistry',
            'description': 'The Hirschmann Award recognizes outstanding achievements in peptide chemistry.',
            'established_year': 1990,
            'display_order': 3
        },
        'goodman': {
            'slug': 'goodman',
            'name': 'Murray Goodman Memorial Award',
            'description': 'The Murray Goodman Memorial Award recognizes scientific excellence and mentorship in peptide science.',
            'established_year': 2009,
            'display_order': 4
        },
        'makineni': {
            'slug': 'makineni',
            'name': 'Rao Makineni Lectureship',
            'description': 'The Rao Makineni Lectureship recognizes an individual who has made outstanding contributions to peptide science.',
            'established_year': 2003,
            'display_order': 5
        },
        'aps': {
            'slug': 'aps',
            'name': 'APS Award',
            'description': 'Special recognition award from the American Peptide Society.',
            'established_year': 2019,
            'display_order': 6
        }
    }
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file containing award data'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the import without saving to database'
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update existing records if found'
        )
        parser.add_argument(
            '--skip-validation',
            action='store_true',
            help='Skip data validation (not recommended)'
        )
    
    def handle(self, *args, **options):
        """Execute the import command."""
        csv_file = options['csv_file']
        dry_run = options['dry_run']
        update_existing = options['update_existing']
        skip_validation = options['skip_validation']
        
        # Validate file exists
        if not os.path.exists(csv_file):
            raise CommandError(f"CSV file not found: {csv_file}")
        
        # Set up logging
        self._setup_logging()
        
        self.stdout.write(f"Starting import from: {csv_file}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be saved"))
        
        # Statistics tracking
        stats = {
            'total_rows': 0,
            'awards_created': 0,
            'awards_updated': 0,
            'recipients_created': 0,
            'recipients_updated': 0,
            'recipients_skipped': 0,
            'errors': 0,
            'validation_errors': []
        }
        
        try:
            # Use atomic transaction for data integrity
            with transaction.atomic():
                # First pass: Create/update award types
                self._process_award_types(dry_run, stats)
                
                # Second pass: Import recipients
                with open(csv_file, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    
                    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is 1)
                        stats['total_rows'] += 1
                        
                        try:
                            self._process_recipient_row(
                                row, row_num, dry_run, update_existing, 
                                skip_validation, stats
                            )
                        except Exception as e:
                            stats['errors'] += 1
                            error_msg = f"Row {row_num}: {str(e)}"
                            logger.error(error_msg)
                            self.stdout.write(self.style.ERROR(error_msg))
                            
                            # Continue with next row unless critical error
                            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                                raise
                
                # Rollback if dry run
                if dry_run:
                    raise CommandError("Dry run completed - rolling back changes")
        
        except CommandError as e:
            if "Dry run completed" in str(e):
                pass  # Expected for dry run
            else:
                raise
        
        # Print summary
        self._print_summary(stats)
    
    def _setup_logging(self):
        """Configure logging for the import process."""
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(
            log_dir, 
            f'awards_import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        )
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        
        self.stdout.write(f"Logging to: {log_file}")
    
    def _process_award_types(self, dry_run, stats):
        """Create or update award types."""
        self.stdout.write("\nProcessing award types...")
        
        for award_key, award_data in self.AWARD_TYPE_MAPPINGS.items():
            # Skip redirect mappings
            if isinstance(award_data, str):
                continue
            
            try:
                award_type, created = AwardType.objects.get_or_create(
                    slug=award_data['slug'],
                    defaults={
                        'name': award_data['name'],
                        'description': award_data.get('description', ''),
                        'established_year': award_data.get('established_year'),
                        'display_order': award_data.get('display_order', 0),
                    }
                )
                
                if created:
                    stats['awards_created'] += 1
                    self.stdout.write(f"  Created award type: {award_type.name}")
                else:
                    # Update if needed
                    updated = False
                    for field in ['name', 'description', 'established_year', 'display_order']:
                        if field in award_data and getattr(award_type, field) != award_data[field]:
                            setattr(award_type, field, award_data[field])
                            updated = True
                    
                    if updated and not dry_run:
                        award_type.save()
                        stats['awards_updated'] += 1
                        self.stdout.write(f"  Updated award type: {award_type.name}")
                
            except Exception as e:
                logger.error(f"Error processing award type {award_key}: {str(e)}")
                raise
    
    def _process_recipient_row(self, row, row_num, dry_run, update_existing, 
                               skip_validation, stats):
        """Process a single recipient row from the CSV."""
        # Extract and clean data
        award_slug = row.get('wpcf-award_name', '').strip().lower()
        year = row.get('wpcf-award-year', '').strip()
        first_name = row.get('wpcf-awardee_fname', '').strip()
        last_name = row.get('wpcf-awardee_lname', '').strip()
        institution = row.get('wpcf-awardee_institution', '').strip()
        biography = row.get('wpcf-awardee_description', '').strip()
        photo_url = row.get('wpcf-awardee_image', '').strip()
        import_id = row.get('ID', '').strip()
        original_url = row.get('Permalink', '').strip()
        slug = row.get('Slug', '').strip()
        
        # Resolve award type mapping
        if award_slug in self.AWARD_TYPE_MAPPINGS:
            mapping = self.AWARD_TYPE_MAPPINGS[award_slug]
            if isinstance(mapping, str):
                # It's a redirect to another award
                award_slug = mapping
                mapping = self.AWARD_TYPE_MAPPINGS[award_slug]
            award_slug = mapping['slug']
        
        # Validate required fields
        if not skip_validation:
            validation_errors = self._validate_recipient_data(
                row_num, award_slug, year, first_name, last_name
            )
            if validation_errors:
                stats['validation_errors'].extend(validation_errors)
                stats['recipients_skipped'] += 1
                for error in validation_errors:
                    self.stdout.write(self.style.WARNING(f"  Validation: {error}"))
                return
        
        # Get award type
        try:
            award_type = AwardType.objects.get(slug=award_slug)
        except AwardType.DoesNotExist:
            error_msg = f"Row {row_num}: Unknown award type '{award_slug}'"
            stats['validation_errors'].append(error_msg)
            stats['recipients_skipped'] += 1
            self.stdout.write(self.style.WARNING(f"  {error_msg}"))
            return
        
        # Convert year to integer
        try:
            year_int = int(year)
        except ValueError:
            error_msg = f"Row {row_num}: Invalid year '{year}'"
            stats['validation_errors'].append(error_msg)
            stats['recipients_skipped'] += 1
            self.stdout.write(self.style.WARNING(f"  {error_msg}"))
            return
        
        # Generate slug if not provided
        if not slug:
            slug = slugify(f"{first_name}-{last_name}-{year}")
        
        # Check for existing recipient
        existing_recipient = None
        try:
            existing_recipient = AwardRecipient.objects.get(
                award_type=award_type,
                year=year_int,
                first_name=first_name,
                last_name=last_name
            )
        except AwardRecipient.DoesNotExist:
            # Also try by import_id if provided
            if import_id:
                try:
                    existing_recipient = AwardRecipient.objects.get(import_id=import_id)
                except AwardRecipient.DoesNotExist:
                    pass
        
        # Create or update recipient
        if existing_recipient and not update_existing:
            stats['recipients_skipped'] += 1
            logger.info(f"Row {row_num}: Skipped existing recipient {existing_recipient}")
            return
        
        recipient_data = {
            'award_type': award_type,
            'year': year_int,
            'first_name': first_name,
            'last_name': last_name,
            'institution': institution,
            'biography': biography,
            'photo_url': photo_url,
            'slug': slug,
            'import_id': import_id,
            'imported_from': 'wordpress',
            'import_date': timezone.now(),
            'original_url': original_url,
        }
        
        if not dry_run:
            if existing_recipient:
                # Update existing
                for field, value in recipient_data.items():
                    if field != 'import_date':  # Don't update import date on updates
                        setattr(existing_recipient, field, value)
                
                try:
                    existing_recipient.full_clean()
                    existing_recipient.save()
                    stats['recipients_updated'] += 1
                    logger.info(f"Row {row_num}: Updated recipient {existing_recipient}")
                except ValidationError as e:
                    error_msg = f"Row {row_num}: Validation error - {str(e)}"
                    stats['validation_errors'].append(error_msg)
                    logger.error(error_msg)
                    raise
            else:
                # Create new
                try:
                    recipient = AwardRecipient(**recipient_data)
                    recipient.full_clean()
                    recipient.save()
                    stats['recipients_created'] += 1
                    logger.info(f"Row {row_num}: Created recipient {recipient}")
                except IntegrityError as e:
                    error_msg = f"Row {row_num}: Integrity error - {str(e)}"
                    stats['validation_errors'].append(error_msg)
                    logger.error(error_msg)
                    raise
                except ValidationError as e:
                    error_msg = f"Row {row_num}: Validation error - {str(e)}"
                    stats['validation_errors'].append(error_msg)
                    logger.error(error_msg)
                    raise
        else:
            # Dry run - just log what would happen
            if existing_recipient:
                self.stdout.write(f"  Would update: {first_name} {last_name} ({award_slug} {year})")
                stats['recipients_updated'] += 1
            else:
                self.stdout.write(f"  Would create: {first_name} {last_name} ({award_slug} {year})")
                stats['recipients_created'] += 1
    
    def _validate_recipient_data(self, row_num, award_slug, year, first_name, last_name):
        """Validate recipient data and return list of errors."""
        errors = []
        
        if not award_slug:
            errors.append(f"Row {row_num}: Missing award type")
        
        if not year:
            errors.append(f"Row {row_num}: Missing year")
        else:
            try:
                year_int = int(year)
                current_year = datetime.now().year
                if year_int < 1970 or year_int > current_year + 1:
                    errors.append(f"Row {row_num}: Invalid year {year} (must be between 1970 and {current_year + 1})")
            except ValueError:
                errors.append(f"Row {row_num}: Invalid year format '{year}'")
        
        if not first_name:
            errors.append(f"Row {row_num}: Missing first name")
        
        if not last_name:
            errors.append(f"Row {row_num}: Missing last name")
        
        return errors
    
    def _print_summary(self, stats):
        """Print import summary."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("IMPORT SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total rows processed: {stats['total_rows']}")
        self.stdout.write(f"Award types created: {stats['awards_created']}")
        self.stdout.write(f"Award types updated: {stats['awards_updated']}")
        self.stdout.write(f"Recipients created: {stats['recipients_created']}")
        self.stdout.write(f"Recipients updated: {stats['recipients_updated']}")
        self.stdout.write(f"Recipients skipped: {stats['recipients_skipped']}")
        self.stdout.write(f"Errors encountered: {stats['errors']}")
        
        if stats['validation_errors']:
            self.stdout.write("\nValidation errors:")
            for error in stats['validation_errors'][:10]:  # Show first 10
                self.stdout.write(f"  - {error}")
            if len(stats['validation_errors']) > 10:
                self.stdout.write(f"  ... and {len(stats['validation_errors']) - 10} more")
        
        self.stdout.write("=" * 60)