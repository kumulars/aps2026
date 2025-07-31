"""
Management command to import symposium images from the media/symposia-images directory
Handles both thumbnail and full-size images for each year (2015, 2017, 2019, 2022, 2023)
"""

import os
import re
from datetime import datetime
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings
from wagtail.images.models import Image
from home.models import SymposiumImage


class Command(BaseCommand):
    help = 'Import symposium images from media/symposia-images directory'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=str,
            help='Import only specific year (e.g., 2015)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Reimport images even if they already exist',
        )

    def handle(self, *args, **options):
        base_path = os.path.join(settings.BASE_DIR, 'media', 'symposia-images')
        
        if not os.path.exists(base_path):
            self.stdout.write(
                self.style.ERROR(f'Symposia images directory not found: {base_path}')
            )
            return

        # Get all year directories
        year_dirs = []
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if os.path.isdir(item_path) and re.match(r'^\d{4}$', item):
                year_dirs.append(item)

        year_dirs.sort()
        
        if options['year']:
            if options['year'] in year_dirs:
                year_dirs = [options['year']]
            else:
                self.stdout.write(
                    self.style.ERROR(f'Year {options["year"]} not found in available years: {year_dirs}')
                )
                return

        self.stdout.write(f'Found symposium years: {year_dirs}')

        total_imported = 0
        total_skipped = 0
        total_errors = 0

        for year in year_dirs:
            self.stdout.write(f'\n=== Processing {year} ===')
            
            year_path = os.path.join(base_path, year)
            full_path = os.path.join(year_path, 'full')
            thumbs_path = os.path.join(year_path, 'thumbs')

            if not os.path.exists(full_path) or not os.path.exists(thumbs_path):
                self.stdout.write(
                    self.style.WARNING(f'Missing full or thumbs directory for {year}')
                )
                continue

            # Get all image files from both directories
            full_files = self._get_image_files(full_path)
            thumb_files = self._get_image_files(thumbs_path)

            self.stdout.write(f'Found {len(full_files)} full images and {len(thumb_files)} thumbnails')

            # Process each image pair
            imported, skipped, errors = self._process_year_images(
                year, full_path, thumbs_path, full_files, thumb_files, options
            )
            
            total_imported += imported
            total_skipped += skipped
            total_errors += errors

        # Summary
        self.stdout.write(f'\n=== IMPORT SUMMARY ===')
        self.stdout.write(f'Total imported: {total_imported}')
        self.stdout.write(f'Total skipped: {total_skipped}')
        self.stdout.write(f'Total errors: {total_errors}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN - No images were actually imported'))

    def _get_image_files(self, directory):
        """Get all image files from directory"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        files = []
        
        for filename in os.listdir(directory):
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                files.append(filename)
        
        return sorted(files)

    def _process_year_images(self, year, full_path, thumbs_path, full_files, thumb_files, options):
        """Process all images for a given year"""
        imported = 0
        skipped = 0
        errors = 0

        # Create a mapping of base filenames to actual files
        full_mapping = self._create_filename_mapping(full_files)
        thumb_mapping = self._create_filename_mapping(thumb_files)

        # Find matching pairs
        all_base_names = set(full_mapping.keys()) | set(thumb_mapping.keys())
        
        for base_name in sorted(all_base_names):
            full_file = full_mapping.get(base_name)
            thumb_file = thumb_mapping.get(base_name)

            if not full_file:
                self.stdout.write(
                    self.style.WARNING(f'No full image found for {base_name}')
                )
                errors += 1
                continue

            if not thumb_file:
                self.stdout.write(
                    self.style.WARNING(f'No thumbnail found for {base_name}')
                )
                # We can still import with just full image

            # Check if already exists
            existing = SymposiumImage.objects.filter(
                year=year, 
                filename=base_name
            ).first()

            if existing and not options['force']:
                self.stdout.write(f'Skipping {base_name} (already exists)')
                skipped += 1
                continue

            if options['dry_run']:
                self.stdout.write(f'Would import: {year} - {base_name}')
                imported += 1
                continue

            # Import the image pair
            try:
                success = self._import_image_pair(
                    year, base_name, full_path, thumbs_path, full_file, thumb_file, existing
                )
                if success:
                    imported += 1
                    self.stdout.write(f'Imported: {base_name}')
                else:
                    errors += 1
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error importing {base_name}: {str(e)}')
                )
                errors += 1

        return imported, skipped, errors

    def _create_filename_mapping(self, files):
        """Create mapping from base filename to actual filename"""
        mapping = {}
        for filename in files:
            # Remove extension and convert to lowercase for matching
            base_name = os.path.splitext(filename.lower())[0]
            mapping[base_name] = filename
        return mapping

    def _import_image_pair(self, year, base_name, full_path, thumbs_path, full_file, thumb_file, existing):
        """Import a single image pair (full + thumbnail)"""
        
        # Import full image to Wagtail
        full_image = self._import_to_wagtail(
            os.path.join(full_path, full_file),
            f'{year}_{base_name}_full',
            f'Symposium {year} - {base_name} (Full)'
        )

        # Import thumbnail to Wagtail
        thumb_image = None
        if thumb_file:
            thumb_image = self._import_to_wagtail(
                os.path.join(thumbs_path, thumb_file),
                f'{year}_{base_name}_thumb',
                f'Symposium {year} - {base_name} (Thumbnail)'
            )

        if not full_image:
            return False

        # Extract date from filename if possible
        event_date = self._extract_date_from_filename(base_name)

        # Create or update SymposiumImage record
        symposium_image, created = SymposiumImage.objects.update_or_create(
            year=year,
            filename=base_name,
            defaults={
                'full_image': full_image,
                'thumbnail_image': thumb_image,
                'event_date': event_date,
                'imported_from': f'media/symposia-images/{year}',
                'display_order': self._calculate_display_order(base_name),
            }
        )

        return True

    def _import_to_wagtail(self, file_path, wagtail_filename, title):
        """Import single file to Wagtail images"""
        try:
            # Check if image already exists in Wagtail
            existing = Image.objects.filter(title=title).first()
            if existing:
                return existing

            with open(file_path, 'rb') as f:
                file_obj = File(f, name=wagtail_filename)
                
                wagtail_image = Image(
                    title=title,
                    file=file_obj
                )
                wagtail_image.save()
                
                return wagtail_image
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to import {file_path}: {str(e)}')
            )
            return None

    def _extract_date_from_filename(self, filename):
        """Try to extract date from filename patterns"""
        # Pattern: 2015_06_15_0002 -> 2015-06-15
        date_pattern = r'(\d{4})_(\d{2})_(\d{2})'
        match = re.search(date_pattern, filename)
        
        if match:
            year, month, day = match.groups()
            try:
                return datetime.strptime(f'{year}-{month}-{day}', '%Y-%m-%d').date()
            except ValueError:
                pass

        # Pattern: 20170617 -> 2017-06-17
        date_pattern2 = r'(\d{4})(\d{2})(\d{2})'
        match2 = re.search(date_pattern2, filename)
        
        if match2:
            year, month, day = match2.groups()
            try:
                return datetime.strptime(f'{year}-{month}-{day}', '%Y-%m-%d').date()
            except ValueError:
                pass

        return None

    def _calculate_display_order(self, filename):
        """Calculate display order based on filename"""
        # Extract numbers from filename for ordering
        numbers = re.findall(r'\d+', filename)
        if numbers:
            # Use the last number as primary sort, filename as secondary
            return int(numbers[-1])
        return 0