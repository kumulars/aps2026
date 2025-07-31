"""
Import award recipient images from the media/award_images directory.

This command matches image files named 'lastname_firstname.jpg' to award recipients
and creates Wagtail Image objects, then assigns them to the recipients.
"""

import os
import logging
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from django.db import transaction
from django.utils.text import slugify
from wagtail.images.models import Image

from home.models import AwardRecipient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to import award recipient images."""
    
    help = 'Import award recipient images from media/award_images directory'
    
    # Content images that aren't recipient photos
    CONTENT_IMAGES = {
        'acs_logo.jpg',
        'merck_logo.jpg', 
        'poly_peptide_logo.jpg',
        'publication.jpg',
        'merrifield_award.jpg',
        'duvigneaud_vincent.jpg',
        'goodman_murray.jpg'
    }
    
    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--images-dir',
            type=str,
            default='media/award_images',
            help='Directory containing award images (default: media/award_images)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run the import without saving to database'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing images'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed matching information'
        )
    
    def handle(self, *args, **options):
        """Execute the image import command."""
        images_dir = options['images_dir']
        dry_run = options['dry_run']
        overwrite = options['overwrite']
        verbose = options['verbose']
        
        # Convert to absolute path
        if not os.path.isabs(images_dir):
            images_dir = os.path.join(os.getcwd(), images_dir)
        
        # Validate directory exists
        if not os.path.exists(images_dir):
            raise CommandError(f"Images directory not found: {images_dir}")
        
        self.stdout.write(f"Importing images from: {images_dir}")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be saved"))
        
        # Statistics tracking
        stats = {
            'total_image_files': 0,
            'content_images_skipped': 0,
            'recipients_matched': 0,
            'recipients_unmatched': 0,
            'images_created': 0,
            'images_updated': 0,
            'images_skipped': 0,
            'errors': 0,
            'matches': [],
            'unmatched_files': [],
            'unmatched_recipients': []
        }
        
        try:
            with transaction.atomic():
                # Get all image files
                image_files = self._get_image_files(images_dir)
                stats['total_image_files'] = len(image_files)
                
                # Get all recipients for matching
                recipients = list(AwardRecipient.objects.all())
                
                # Process image files
                for image_file in image_files:
                    try:
                        self._process_image_file(
                            image_file, recipients, images_dir, 
                            dry_run, overwrite, verbose, stats
                        )
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = f"Error processing {image_file}: {str(e)}"
                        logger.error(error_msg)
                        self.stdout.write(self.style.ERROR(error_msg))
                
                # Find recipients without images
                self._find_unmatched_recipients(recipients, stats)
                
                # Rollback if dry run
                if dry_run:
                    raise CommandError("Dry run completed - rolling back changes")
        
        except CommandError as e:
            if "Dry run completed" in str(e):
                pass  # Expected for dry run
            else:
                raise
        
        # Print summary
        self._print_summary(stats, verbose)
    
    def _get_image_files(self, images_dir):
        """Get all image files from the directory."""
        supported_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        image_files = []
        
        for filename in os.listdir(images_dir):
            if Path(filename).suffix.lower() in supported_extensions:
                image_files.append(filename)
        
        return sorted(image_files)
    
    def _process_image_file(self, filename, recipients, images_dir, 
                           dry_run, overwrite, verbose, stats):
        """Process a single image file."""
        file_path = os.path.join(images_dir, filename)
        
        # Skip content images
        if filename in self.CONTENT_IMAGES:
            stats['content_images_skipped'] += 1
            if verbose:
                self.stdout.write(f"  Skipped content image: {filename}")
            return
        
        # Try to match to recipient
        recipient = self._match_filename_to_recipient(filename, recipients)
        
        if not recipient:
            stats['recipients_unmatched'] += 1
            stats['unmatched_files'].append(filename)
            if verbose:
                self.stdout.write(
                    self.style.WARNING(f"  No match found for: {filename}")
                )
            return
        
        stats['recipients_matched'] += 1
        stats['matches'].append((filename, recipient))
        
        # Check if recipient already has an image
        if recipient.photo and not overwrite:
            stats['images_skipped'] += 1
            if verbose:
                self.stdout.write(
                    f"  Skipped (has image): {filename} -> {recipient.full_name}"
                )
            return
        
        if not dry_run:
            # Create or update Wagtail Image
            image_obj = self._create_wagtail_image(
                file_path, filename, recipient, overwrite
            )
            
            if image_obj:
                # Assign to recipient
                old_image = recipient.photo
                recipient.photo = image_obj
                recipient.save(update_fields=['photo'])
                
                if old_image and overwrite:
                    stats['images_updated'] += 1
                    action = "Updated"
                else:
                    stats['images_created'] += 1
                    action = "Created"
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {action}: {filename} -> {recipient.full_name}"
                    )
                )
            else:
                stats['errors'] += 1
        else:
            # Dry run output
            action = "Update" if recipient.photo else "Create"
            self.stdout.write(
                f"  Would {action.lower()}: {filename} -> {recipient.full_name}"
            )
            if recipient.photo:
                stats['images_updated'] += 1
            else:
                stats['images_created'] += 1
    
    def _match_filename_to_recipient(self, filename, recipients):
        """Match an image filename to a recipient."""
        # Remove extension and convert to lowercase
        name_part = Path(filename).stem.lower()
        
        # Manual mappings for tricky cases
        manual_mappings = {
            'beck_sickinger': ('Beck-Sickinger', 'Annette'),
            'dela_fuente_cesar': ('de la Fuente', 'César'),
            'gierasch_leila': ('Gierasch', 'Lila'),  # Different spelling
            'hruby_victor_awardee': ('Hruby', 'Victor J.'),
            'kelly_jeffery': ('Kelly', 'Jeffery W.'),
            'kent_stephen': ('Kent', 'Stephen B.H.'),
            'lam_kit': ('Lam', 'Kit Sang'),
            'lubell_william': ('Lubell', 'William D.'),
            'parkinson_betsy': ('Parkinson', 'Elizabeth \'Betsy\''),
            'pentelute_bradley': ('Pentelute', 'Bradley L.'),
            'tam_james': ('Tam', 'James P.'),
            'vanderdonk_wilfred': ('van der Donk', 'Wilfred'),
        }
        
        # Check manual mappings first
        if name_part in manual_mappings:
            last_name, first_name = manual_mappings[name_part]
            for recipient in recipients:
                if (recipient.last_name == last_name and 
                    recipient.first_name == first_name):
                    return recipient
        
        # Try exact lastname_firstname match
        for recipient in recipients:
            expected_name = f"{recipient.last_name.lower()}_{recipient.first_name.lower()}"
            expected_name = expected_name.replace(' ', '_').replace('-', '_')
            
            if name_part == expected_name:
                return recipient
        
        # Try with normalized names (remove special characters)
        name_normalized = self._normalize_name(name_part)
        
        for recipient in recipients:
            expected_name = f"{recipient.last_name.lower()}_{recipient.first_name.lower()}"
            expected_normalized = self._normalize_name(expected_name)
            
            if name_normalized == expected_normalized:
                return recipient
        
        # Try partial matches (starts with lastname)
        for recipient in recipients:
            lastname_normalized = self._normalize_name(recipient.last_name.lower())
            firstname_normalized = self._normalize_name(recipient.first_name.lower())
            
            if (name_normalized.startswith(lastname_normalized) and 
                firstname_normalized in name_normalized):
                return recipient
        
        # Try matching just by last name + first initial
        for recipient in recipients:
            lastname_lower = self._normalize_name(recipient.last_name.lower())
            first_initial = recipient.first_name[0].lower() if recipient.first_name else ''
            
            if (name_normalized.startswith(lastname_lower) and 
                first_initial and first_initial in name_normalized):
                return recipient
        
        return None
    
    def _normalize_name(self, name):
        """Normalize a name by removing special characters and extra spaces."""
        # Remove quotes, periods, and other punctuation
        name = name.replace("'", "").replace('"', "").replace('.', '')
        name = name.replace('-', '_').replace(' ', '_')
        # Remove multiple underscores
        while '__' in name:
            name = name.replace('__', '_')
        # Remove non-alphanumeric characters except underscores
        name = ''.join(c for c in name if c.isalnum() or c == '_')
        return name.strip('_')
    
    def _create_wagtail_image(self, file_path, filename, recipient, overwrite):
        """Create a Wagtail Image object from the file."""
        try:
            # Generate title for the image
            title = f"{recipient.full_name} - {recipient.award_type.name} {recipient.year}"
            
            # Check if image already exists by title (to avoid duplicates)
            existing_image = None
            if overwrite:
                try:
                    existing_image = Image.objects.get(title=title)
                except Image.DoesNotExist:
                    pass
            
            if existing_image:
                # Update existing image
                with open(file_path, 'rb') as f:
                    existing_image.file.save(filename, File(f), save=True)
                return existing_image
            else:
                # Create new image
                with open(file_path, 'rb') as f:
                    image = Image(
                        title=title,
                        file=File(f, name=filename)
                    )
                    image.save()
                return image
                
        except Exception as e:
            logger.error(f"Error creating Wagtail image for {filename}: {str(e)}")
            return None
    
    def _find_unmatched_recipients(self, recipients, stats):
        """Find recipients without matched images."""
        for recipient in recipients:
            if not any(recipient == match[1] for match in stats['matches']):
                stats['unmatched_recipients'].append(recipient)
    
    def _print_summary(self, stats, verbose):
        """Print import summary."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("IMAGE IMPORT SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Total image files found: {stats['total_image_files']}")
        self.stdout.write(f"Content images skipped: {stats['content_images_skipped']}")
        self.stdout.write(f"Recipients matched: {stats['recipients_matched']}")
        self.stdout.write(f"Recipients unmatched: {stats['recipients_unmatched']}")
        self.stdout.write(f"Images created: {stats['images_created']}")
        self.stdout.write(f"Images updated: {stats['images_updated']}")
        self.stdout.write(f"Images skipped: {stats['images_skipped']}")
        self.stdout.write(f"Errors encountered: {stats['errors']}")
        
        if verbose and stats['unmatched_files']:
            self.stdout.write(f"\nUnmatched image files ({len(stats['unmatched_files'])}):")
            for filename in stats['unmatched_files'][:10]:  # Show first 10
                self.stdout.write(f"  - {filename}")
            if len(stats['unmatched_files']) > 10:
                self.stdout.write(f"  ... and {len(stats['unmatched_files']) - 10} more")
        
        if verbose and stats['unmatched_recipients']:
            self.stdout.write(f"\nRecipients without images ({len(stats['unmatched_recipients'])}):")
            for recipient in stats['unmatched_recipients'][:10]:  # Show first 10
                expected_filename = f"{recipient.last_name.lower()}_{recipient.first_name.lower()}.jpg"
                self.stdout.write(f"  - {recipient.full_name} (expected: {expected_filename})")
            if len(stats['unmatched_recipients']) > 10:
                self.stdout.write(f"  ... and {len(stats['unmatched_recipients']) - 10} more")
        
        self.stdout.write("=" * 60)