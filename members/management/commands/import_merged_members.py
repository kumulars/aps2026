#!/usr/bin/env python3
"""
Django management command to import merged membership data
"""

import pandas as pd
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from members.models import Member, MembershipLevel


class Command(BaseCommand):
    help = 'Import merged membership data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='membership/members/aps_members_merged.csv',
            help='Path to the merged CSV file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually importing data'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No data will be imported')
            )
        
        try:
            # Load the merged data
            self.stdout.write(f'Loading data from {file_path}...')
            df = pd.read_csv(file_path)
            self.stdout.write(f'Loaded {len(df)} records')
            
            # Create default membership level if it doesn't exist
            if not dry_run:
                default_level, created = MembershipLevel.objects.get_or_create(
                    name='Standard Member',
                    defaults={
                        'description': 'Standard APS membership',
                        'annual_dues': 150.00
                    }
                )
                if created:
                    self.stdout.write('Created default membership level')
            
            # Import records
            imported_count = 0
            updated_count = 0
            error_count = 0
            
            with transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        # Skip rows with no email
                        email = self._clean_email(row.get('email'))
                        if not email:
                            continue
                        
                        # Prepare member data
                        member_data = self._prepare_member_data(row)
                        
                        if not dry_run:
                            # Check if member already exists
                            member, created = Member.objects.get_or_create(
                                email=email,
                                defaults=member_data
                            )
                            
                            if created:
                                member.membership_level = default_level
                                member.save()
                                imported_count += 1
                                if imported_count % 100 == 0:
                                    self.stdout.write(f'Imported {imported_count} members...')
                            else:
                                # Update existing member with new data
                                for field, value in member_data.items():
                                    if value and not getattr(member, field):
                                        setattr(member, field, value)
                                member.save()
                                updated_count += 1
                        else:
                            imported_count += 1
                    
                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.ERROR(f'Error processing row {index}: {str(e)}')
                        )
                        continue
            
            # Report results
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nImport completed!\n'
                    f'New members: {imported_count}\n'
                    f'Updated members: {updated_count}\n'
                    f'Errors: {error_count}'
                )
            )
            
        except FileNotFoundError:
            raise CommandError(f'File not found: {file_path}')
        except Exception as e:
            raise CommandError(f'Import failed: {str(e)}')

    def _clean_email(self, email):
        """Clean and validate email"""
        if pd.isna(email):
            return None
        email = str(email).strip().lower()
        return email if '@' in email else None

    def _clean_string(self, value):
        """Clean string values"""
        if pd.isna(value):
            return ''
        return str(value).strip()

    def _clean_phone(self, phone):
        """Clean phone number"""
        if pd.isna(phone):
            return ''
        return str(phone).strip()

    def _parse_year(self, year):
        """Parse PhD year"""
        if pd.isna(year):
            return None
        try:
            year_int = int(float(year))
            return year_int if 1900 <= year_int <= 2030 else None
        except (ValueError, TypeError):
            return None

    def _map_affiliation_type(self, aff_type):
        """Map legacy affiliation types to model choices"""
        if pd.isna(aff_type):
            return ''
        
        aff_type = str(aff_type).lower().strip()
        mapping = {
            'academic': 'academic',
            'university': 'academic',
            'college': 'academic',
            'industry': 'industry',
            'company': 'industry',
            'corporate': 'industry',
            'government': 'government',
            'federal': 'government',
            'state': 'government',
            'student': 'student',
            'graduate': 'student',
            'undergraduate': 'student',
            'retired': 'retired',
            'emeritus': 'retired',
        }
        
        for key, value in mapping.items():
            if key in aff_type:
                return value
        
        return 'other'

    def _determine_status(self, row):
        """Determine membership status based on available data"""
        from django.conf import settings
        
        # If free membership is enabled, make everyone active
        if getattr(settings, 'APS_FREE_MEMBERSHIP', False):
            return 'active'
        
        # Original logic for paid memberships
        data_source = self._clean_string(row.get('data_source', ''))
        
        if data_source == 'legacy_only':
            return 'inactive'  # Legacy members likely inactive
        elif data_source in ['wordpress', 'merged']:
            return 'active'    # WordPress members likely active
        else:
            return 'pending'

    def _prepare_member_data(self, row):
        """Prepare member data dictionary from CSV row"""
        return {
            'first_name': self._clean_string(row.get('first_name', '')),
            'last_name': self._clean_string(row.get('last_name', '')),
            'title': self._clean_string(row.get('legacy_title', '')),
            'phone': self._clean_phone(row.get('legacy_phone', '')),
            'address_1': self._clean_string(row.get('legacy_address_1', '')),
            'address_2': self._clean_string(row.get('legacy_address_2', '')),
            'city': self._clean_string(row.get('legacy_city', '')),
            'state': self._clean_string(row.get('legacy_state', '')),
            'zip_code': self._clean_string(row.get('legacy_zip', '')),
            'country': self._clean_string(row.get('legacy_country', '')),
            'affiliation': self._clean_string(row.get('legacy_affiliation', '')),
            'affiliation_type': self._map_affiliation_type(row.get('legacy_affiliation_type')),
            'phd_year': self._parse_year(row.get('legacy_phd_year')),
            'status': self._determine_status(row),
            'data_source': self._clean_string(row.get('data_source', 'imported')),
            'import_date': timezone.now(),
            'legacy_id': self._clean_string(row.get('legacy_id', '')),
            'legacy_match_type': self._clean_string(row.get('legacy_match_type', '')),
            'legacy_match_confidence': row.get('legacy_match_confidence') if not pd.isna(row.get('legacy_match_confidence')) else None,
            'wp_user_id': row.get('ID') if not pd.isna(row.get('ID')) else None,
            'wp_user_login': self._clean_string(row.get('user_login', '')),
        }