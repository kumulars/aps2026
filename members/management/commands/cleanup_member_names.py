"""
Management command to clean up member records with missing names.
This will attempt to extract names from email addresses and hide unusable records.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from members.models import Member
import re


class Command(BaseCommand):
    help = 'Clean up member records with missing first/last names'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )
        parser.add_argument(
            '--hide-unusable',
            action='store_true',
            help='Hide members from directory if no name can be extracted',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hide_unusable = options['hide_unusable']
        
        # Find members with missing names
        missing_names = Member.objects.filter(
            Q(first_name='') | Q(first_name__isnull=True),
            Q(last_name='') | Q(last_name__isnull=True)
        )
        
        self.stdout.write(f"Found {missing_names.count()} members with missing names")
        
        extracted = 0
        hidden = 0
        skipped = 0
        
        for member in missing_names:
            email = member.email.strip().lower()
            
            if not email or '@' not in email:
                if hide_unusable:
                    if not dry_run:
                        member.directory_visible = False
                        member.save()
                    hidden += 1
                    self.stdout.write(f"Hidden: ID {member.id} (no email)")
                else:
                    skipped += 1
                continue
            
            # Extract local part of email
            local_part = email.split('@')[0]
            
            # Try different extraction patterns
            first_name = ""
            last_name = ""
            
            # Pattern 1: firstname.lastname
            if '.' in local_part and not local_part[0].isdigit():
                parts = [p for p in local_part.split('.') if p]
                if len(parts) >= 2:
                    potential_first = parts[0].replace('_', '').replace('-', '')
                    potential_last = parts[1].replace('_', '').replace('-', '')
                    
                    # Check if they look like names (alpha, reasonable length)
                    if (potential_first.isalpha() and len(potential_first) > 1 and
                        potential_last.isalpha() and len(potential_last) > 1 and
                        len(potential_first) < 20 and len(potential_last) < 20):
                        first_name = potential_first.title()
                        last_name = potential_last.title()
            
            # Pattern 2: firstinitiallastname (like a.bajpai)
            elif '.' in local_part and len(local_part.split('.')) == 2:
                parts = local_part.split('.')
                if len(parts[0]) == 1 and len(parts[1]) > 2 and parts[1].isalpha():
                    first_name = parts[0].upper()
                    last_name = parts[1].title()
            
            # If we extracted names, update the record
            if first_name and last_name:
                if not dry_run:
                    member.first_name = first_name
                    member.last_name = last_name
                    member.save()
                extracted += 1
                self.stdout.write(f"Extracted: {email} -> {first_name} {last_name}")
            else:
                # Couldn't extract names
                if hide_unusable:
                    if not dry_run:
                        member.directory_visible = False
                        member.save()
                    hidden += 1
                    self.stdout.write(f"Hidden: ID {member.id} ({email})")
                else:
                    skipped += 1
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSummary {'(DRY RUN)' if dry_run else ''}:\n"
                f"  Names extracted: {extracted}\n"
                f"  Records hidden: {hidden}\n"
                f"  Records skipped: {skipped}\n"
                f"  Total processed: {extracted + hidden + skipped}"
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "This was a dry run. Use without --dry-run to make changes."
                )
            )