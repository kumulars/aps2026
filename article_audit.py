#!/usr/bin/env python3
"""
Article Content Audit Script
Compares database articles with CSV source data to identify discrepancies
"""

import os
import sys
import django
import csv
from difflib import SequenceMatcher

# Setup Django
sys.path.append('/Users/larssahl/documents/wagtail/aps2026')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aps2026_site.settings.dev')
django.setup()

from home.models import NewsResearchItem

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a, b).ratio()

def strip_html_basic(text):
    """Basic HTML tag removal for comparison"""
    import re
    return re.sub(r'<[^>]+>', '', text).strip()

def audit_articles():
    """Compare all database articles with CSV sources"""
    
    csv_files = [
        '/Users/larssahl/documents/wagtail/aps2026/import_files/APS-News-Export-2025-July-20-1447.csv',
        '/Users/larssahl/documents/wagtail/aps2026/import_files/backup_14_new_items.csv'
    ]
    
    # Load CSV data
    csv_articles = {}
    
    for csv_file in csv_files:
        if os.path.exists(csv_file):
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    title = row.get('news_item_short_title', '').strip()
                    if title:
                        csv_articles[title] = {
                            'pi_first_name': row.get('news_item_pi_first_name', '').strip(),
                            'pi_last_name': row.get('news_item_pi_last_name', '').strip(),
                            'pi_institution': row.get('news_item_pi_institution', '').strip(),
                            'full_text': row.get('news_item_full_text', '').strip(),
                            'blurb': row.get('news_item_blurb', '').strip(),
                            'authors': row.get('news_item_authors', '').strip(),
                            'citation': row.get('news_item_citation', '').strip(),
                            'source_file': os.path.basename(csv_file)
                        }
    
    # Get database articles
    db_articles = NewsResearchItem.objects.all()
    
    issues = []
    
    print("🔍 ARTICLE CONTENT AUDIT REPORT")
    print("=" * 50)
    
    for db_article in db_articles:
        title = db_article.news_item_short_title
        
        if title in csv_articles:
            csv_data = csv_articles[title]
            
            # Compare key fields
            discrepancies = []
            
            # Check PI name
            db_pi = f"{db_article.news_item_pi_first_name} {db_article.news_item_pi_last_name}".strip()
            csv_pi = f"{csv_data['pi_first_name']} {csv_data['pi_last_name']}".strip()
            if db_pi != csv_pi and csv_pi.strip():
                discrepancies.append(f"PI Name: DB='{db_pi}' vs CSV='{csv_pi}'")
            
            # Check institution
            if db_article.news_item_pi_institution != csv_data['pi_institution'] and csv_data['pi_institution']:
                discrepancies.append(f"Institution: DB='{db_article.news_item_pi_institution}' vs CSV='{csv_data['pi_institution']}'")
            
            # Check content similarity
            db_content = strip_html_basic(db_article.news_item_full_text or '')
            csv_content = strip_html_basic(csv_data['full_text'] or '')
            
            content_similarity = similarity(db_content, csv_content)
            
            if content_similarity < 0.8:  # Less than 80% similar
                discrepancies.append(f"Content similarity: {content_similarity:.2%}")
                
                # Show content preview
                db_preview = db_content[:100] + "..." if len(db_content) > 100 else db_content
                csv_preview = csv_content[:100] + "..." if len(csv_content) > 100 else csv_content
                discrepancies.append(f"DB Content: {db_preview}")
                discrepancies.append(f"CSV Content: {csv_preview}")
            
            if discrepancies:
                print(f"\n❌ ISSUES FOUND: {title}")
                print(f"   Source: {csv_data['source_file']}")
                for issue in discrepancies:
                    print(f"   - {issue}")
                issues.append({
                    'title': title,
                    'issues': discrepancies,
                    'source_file': csv_data['source_file']
                })
        else:
            print(f"\n⚠️  NOT FOUND IN CSV: {title}")
            issues.append({
                'title': title,
                'issues': ['Article not found in any CSV source'],
                'source_file': 'None'
            })
    
    # Summary
    print(f"\n" + "=" * 50)
    print(f"📊 AUDIT SUMMARY")
    print(f"Total articles in database: {db_articles.count()}")
    print(f"Total articles in CSV files: {len(csv_articles)}")
    print(f"Articles with issues: {len(issues)}")
    
    if issues:
        print(f"\n🚨 ARTICLES REQUIRING ATTENTION:")
        for i, issue in enumerate(issues, 1):
            print(f"{i}. {issue['title']} ({len(issue['issues'])} issues)")
    
    return issues

if __name__ == "__main__":
    audit_articles()