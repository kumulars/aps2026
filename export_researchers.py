#!/usr/bin/env python
import os
import sys
import django
import csv
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aps2026_site.settings.dev')
django.setup()

from home.models import Researcher, ResearchArea

# Get all researchers
researchers = Researcher.objects.all().prefetch_related('research_areas').select_related('member')

# Prepare CSV file
filename = f'peptide_links_researchers_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'

# Define all fields
fieldnames = [
    'id',
    'first_name',
    'last_name', 
    'title',
    'display_name',
    'institution',
    'department',
    'country',
    'state_province',
    'city',
    'location_display',
    'website_url',
    'institutional_email',
    'orcid_id',
    'research_areas',
    'research_keywords',
    'public_bio',
    'pubmed_search_term',
    'pubmed_url',
    'google_scholar_url',
    'is_active',
    'is_verified',
    'website_status',
    'created_at',
    'updated_at',
    'last_verified',
    'last_link_check',
    'admin_notes',
    'has_member_account',
    'member_email',
    'member_status'
]

# Write CSV
with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    
    for researcher in researchers:
        row = {
            'id': researcher.id,
            'first_name': researcher.first_name,
            'last_name': researcher.last_name,
            'title': researcher.title or '',
            'display_name': researcher.display_name,
            'institution': researcher.institution or '',
            'department': researcher.department or '',
            'country': researcher.country,
            'state_province': researcher.state_province or '',
            'city': researcher.city or '',
            'location_display': researcher.location_display,
            'website_url': researcher.website_url or '',
            'institutional_email': researcher.institutional_email or '',
            'orcid_id': researcher.orcid_id or '',
            'research_areas': ', '.join([area.name for area in researcher.research_areas.all()]),
            'research_keywords': researcher.research_keywords or '',
            'public_bio': researcher.public_bio or '',
            'pubmed_search_term': researcher.pubmed_search_term or '',
            'pubmed_url': researcher.pubmed_url or '',
            'google_scholar_url': researcher.google_scholar_url or '',
            'is_active': researcher.is_active,
            'is_verified': researcher.is_verified,
            'website_status': researcher.website_status or '',
            'created_at': researcher.created_at.isoformat() if researcher.created_at else '',
            'updated_at': researcher.updated_at.isoformat() if researcher.updated_at else '',
            'last_verified': researcher.last_verified.isoformat() if researcher.last_verified else '',
            'last_link_check': researcher.last_link_check.isoformat() if researcher.last_link_check else '',
            'admin_notes': researcher.admin_notes or '',
            'has_member_account': 'Yes' if researcher.member else 'No',
            'member_email': researcher.member.email if researcher.member else '',
            'member_status': researcher.member.status if researcher.member else ''
        }
        writer.writerow(row)

print(f"✅ Export complete: {filename}")
print(f"Total researchers exported: {researchers.count()}")

# Show summary statistics
active_count = researchers.filter(is_active=True).count()
verified_count = researchers.filter(is_verified=True).count()
with_members = researchers.filter(member__isnull=False).count()

print(f"\nStatistics:")
print(f"- Active researchers: {active_count}")
print(f"- Verified researchers: {verified_count}")
print(f"- With member accounts: {with_members}")

# Show first few rows as preview
print("\nFirst 10 researchers preview:")
for i, r in enumerate(researchers[:10], 1):
    areas = ', '.join([a.name for a in r.research_areas.all()]) if r.research_areas.exists() else 'None'
    print(f"{i}. {r.display_name} - {r.institution} ({r.location_display})")
    if areas != 'None':
        print(f"   Research areas: {areas}")