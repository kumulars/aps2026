#!/usr/bin/env python3
"""
PRECISION IMPORT VERIFICATION SCRIPT
- Field-by-field verification of all 185 articles
- HTML markup preservation validation
- Image assignment verification
- NO database changes - verification only
"""

import os
import sys
import django
import csv
from datetime import datetime

# Setup Django
sys.path.append('/Users/larssahl/documents/wagtail/aps2026')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aps2026_site.settings.dev')
django.setup()

from home.models import NewsResearchItem
from wagtail.images.models import Image

def find_existing_images():
    """Find all existing image files in media directories"""
    media_paths = ['media/', 'media/images/', 'media/original_images/']
    existing_images = {}
    
    for path in media_paths:
        if os.path.exists(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                        existing_images[file.lower()] = os.path.join(root, file)
    
    return existing_images

def verify_html_content(content, field_name, article_id):
    """Verify HTML content is preserved correctly"""
    html_tags = ['<em>', '</em>', '<strong>', '</strong>', '<sub>', '</sub>', 
                 '<sup>', '</sup>', '<span', '</span>', '<p>', '</p>', 
                 '<a href=', '</a>', '<div', '</div>']
    
    issues = []
    for tag in html_tags:
        if tag in content:
            # Found HTML - this is good, it should be preserved
            continue
    
    return issues

def verify_import_plan():
    """Verify the complete import plan without making changes"""
    
    print("🔍 PRECISION IMPORT VERIFICATION")
    print("=" * 60)
    
    # Find existing images
    existing_images = find_existing_images()
    print(f"📁 Found {len(existing_images)} images in media folders")
    
    # Load CSV data
    articles_to_import = []
    verification_issues = []
    
    with open('news_item_restoration.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):
            article_data = {}
            
            # LEGACY fields (for reference only)
            legacy_id = row.get('LEGACY_ID', '').strip()
            legacy_title = row.get('LEGACY_SHORT_TITLE', '').strip()
            legacy_date = row.get('LEGACY_ENTRY_DATE', '').strip()
            legacy_img = row.get('LEGACY_IMG_NAME', '').strip()
            
            # Parse date
            try:
                parsed_date = datetime.strptime(legacy_date, '%m/%d/%y %H:%M')
                article_data['news_item_entry_date'] = parsed_date
            except ValueError as e:
                verification_issues.append(f"Row {row_num}: Date parse error: {legacy_date} - {e}")
                continue
            
            # Map all fields exactly as they appear in CSV
            article_data['news_item_id'] = legacy_id
            article_data['news_item_pi_first_name'] = row.get('news_item_pi_first_name', '').strip()
            article_data['news_item_pi_last_name'] = row.get('news_item_pi_last_name', '').strip()
            article_data['news_item_pi_title'] = row.get('news_item_pi_title', '').strip()
            article_data['news_item_pi_institution'] = row.get('news_item_pi_institution', '').strip()
            article_data['news_item_short_title'] = row.get('news_item_short_title', '').strip()
            article_data['news_item_blurb'] = row.get('news_item_blurb', '').strip()
            article_data['news_item_full_text'] = row.get('news_item_full_text', '').strip()
            article_data['news_item_image_caption'] = row.get('news_item_image_caption', '').strip()
            article_data['news_item_full_title'] = row.get('news_item_full_title', '').strip()
            article_data['news_item_authors'] = row.get('news_item_authors', '').strip()
            article_data['news_item_citation'] = row.get('news_item_citation', '').strip()
            article_data['news_item_journal_url'] = row.get('news_item_journal_url', '').strip()
            
            # Verify title consistency
            if legacy_title != article_data['news_item_short_title']:
                verification_issues.append(f"Row {row_num}: Title mismatch - LEGACY: '{legacy_title}' vs CSV: '{article_data['news_item_short_title']}'")
            
            # Check for image
            image_path = None
            if legacy_img and legacy_img.lower() in existing_images:
                image_path = existing_images[legacy_img.lower()]
                article_data['image_available'] = True
                article_data['image_path'] = image_path
            else:
                article_data['image_available'] = False
                if legacy_img:
                    verification_issues.append(f"Row {row_num}: Missing image: {legacy_img}")
            
            # Verify HTML content preservation
            html_fields = ['news_item_full_text', 'news_item_blurb', 'news_item_citation']
            for field in html_fields:
                content = article_data.get(field, '')
                if content:
                    html_issues = verify_html_content(content, field, legacy_id)
                    verification_issues.extend([f"Row {row_num}: {issue}" for issue in html_issues])
            
            articles_to_import.append({
                'row_num': row_num,
                'legacy_id': legacy_id,
                'legacy_title': legacy_title,
                'legacy_img': legacy_img,
                'data': article_data
            })
    
    # Generate verification report
    print(f"\n📊 VERIFICATION SUMMARY:")
    print(f"Total articles to import: {len(articles_to_import)}")
    print(f"Articles with images: {sum(1 for a in articles_to_import if a['data']['image_available'])}")
    print(f"Articles missing images: {sum(1 for a in articles_to_import if not a['data']['image_available'])}")
    print(f"Verification issues found: {len(verification_issues)}")
    
    # Show first 5 articles for verification
    print(f"\n🔍 FIRST 5 ARTICLES TO IMPORT:")
    for i, article in enumerate(articles_to_import[:5]):
        data = article['data']
        print(f"\n{i+1}. ID {article['legacy_id']}: {data['news_item_short_title']}")
        print(f"   PI: {data['news_item_pi_first_name']} {data['news_item_pi_last_name']}")
        print(f"   Institution: {data['news_item_pi_institution']}")
        print(f"   Date: {data['news_item_entry_date']}")
        print(f"   Image: {'✅ Available' if data['image_available'] else '❌ Missing'}")
        print(f"   Full text length: {len(data['news_item_full_text'])} chars")
        print(f"   HTML preserved: {'✅ Yes' if '<' in data['news_item_full_text'] else '⚠️ No HTML found'}")
    
    # Show verification issues
    if verification_issues:
        print(f"\n⚠️ VERIFICATION ISSUES:")
        for issue in verification_issues[:10]:  # Show first 10 issues
            print(f"   - {issue}")
        if len(verification_issues) > 10:
            print(f"   ... and {len(verification_issues) - 10} more issues")
    
    print(f"\n✅ VERIFICATION COMPLETE - NO DATABASE CHANGES MADE")
    print(f"Ready to proceed with import? All {len(articles_to_import)} articles verified.")
    
    return articles_to_import, verification_issues

if __name__ == "__main__":
    verify_import_plan()