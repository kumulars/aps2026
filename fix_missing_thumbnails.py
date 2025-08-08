#!/usr/bin/env python
"""
Script to create missing thumbnails and update database entries
"""

import os
import sys
import django
from PIL import Image as PILImage

# Setup Django
sys.path.append('/Users/larssahl/documents/wagtail/aps2026')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aps2026_site.settings.dev')
django.setup()

from django.core.files import File
from wagtail.images.models import Image
from home.models import SymposiumImage

def create_thumbnail(source_path, target_path, size=(125, 86)):
    """Create a thumbnail from a full-size image"""
    try:
        with PILImage.open(source_path) as img:
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Create thumbnail maintaining aspect ratio
            img.thumbnail(size, PILImage.Resampling.LANCZOS)
            
            # Save thumbnail
            img.save(target_path, 'JPEG', quality=85)
            return True
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return False

def main():
    # Define the missing thumbnails
    missing_thumbs = [
        ('henriques_sonia_20190624_0010', 'jpg', 'JPG'),
        ('raskatov_jevgenij_20190623_0034', 'jpg', 'JPG'),
        ('zondlo_neal_0130', 'jpg', 'JPG')
    ]
    
    base_path = '/Users/larssahl/documents/wagtail/aps2026/media/symposia-images/2019'
    
    for filename, full_ext, thumb_ext in missing_thumbs:
        print(f"\nProcessing {filename}...")
        
        # Paths
        full_path = os.path.join(base_path, 'full', f'{filename}.{full_ext}')
        thumb_path = os.path.join(base_path, 'thumbs', f'{filename}.{thumb_ext}')
        
        # Check if full image exists
        if not os.path.exists(full_path):
            print(f"  ERROR: Full image not found at {full_path}")
            continue
        
        # Create thumbnail file
        print(f"  Creating thumbnail from full image...")
        if create_thumbnail(full_path, thumb_path):
            print(f"  Thumbnail created at {thumb_path}")
        else:
            print(f"  ERROR: Failed to create thumbnail")
            continue
        
        # Update database - add thumbnail to Wagtail
        try:
            # Get the SymposiumImage record
            symposium_img = SymposiumImage.objects.filter(year='2019', filename=filename).first()
            
            if not symposium_img:
                print(f"  ERROR: Database entry not found for {filename}")
                continue
            
            # Import thumbnail to Wagtail
            with open(thumb_path, 'rb') as f:
                file_obj = File(f, name=f'2019_{filename}_thumb')
                
                wagtail_thumb = Image(
                    title=f'Symposium 2019 - {filename} (Thumbnail)',
                    file=file_obj
                )
                wagtail_thumb.save()
                
                # Update SymposiumImage with the thumbnail
                symposium_img.thumbnail_image = wagtail_thumb
                symposium_img.save()
                
                print(f"  Database updated with thumbnail")
                
        except Exception as e:
            print(f"  ERROR updating database: {e}")
    
    print("\n" + "="*60)
    print("Thumbnail creation and database update complete!")
    
    # Verify the fixes
    print("\nVerifying fixes:")
    for filename, _, _ in missing_thumbs:
        img = SymposiumImage.objects.filter(year='2019', filename=filename).first()
        if img:
            print(f"  {filename}: Has thumbnail = {img.thumbnail_image is not None}")

if __name__ == '__main__':
    main()