#!/usr/bin/env python3
"""
APS Membership Data Merger
==========================

This script merges WordPress membership export with legacy Excel membership data,
combining the best of both datasets while preserving data integrity.

Author: Claude Code Assistant
Date: 2025-01-19
"""

import pandas as pd
import numpy as np
import re
from pathlib import Path
from difflib import SequenceMatcher
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MembershipDataMerger:
    def __init__(self, csv_file_path, excel_file_path):
        self.csv_file_path = Path(csv_file_path)
        self.excel_file_path = Path(excel_file_path)
        self.wordpress_data = None
        self.legacy_data = None
        self.merged_data = None
        self.merge_stats = {
            'total_wordpress': 0,
            'total_legacy': 0,
            'email_matches': 0,
            'name_matches': 0,
            'wordpress_only': 0,
            'legacy_only': 0,
            'enriched_records': 0
        }
    
    def load_data(self):
        """Load both data files"""
        logger.info("Loading WordPress CSV data...")
        self.wordpress_data = pd.read_csv(self.csv_file_path)
        self.merge_stats['total_wordpress'] = len(self.wordpress_data)
        logger.info(f"Loaded {len(self.wordpress_data)} WordPress records")
        
        logger.info("Loading Legacy Excel data...")
        self.legacy_data = pd.read_excel(self.excel_file_path)
        # Clean column names (remove leading/trailing spaces)
        self.legacy_data.columns = self.legacy_data.columns.str.strip()
        self.merge_stats['total_legacy'] = len(self.legacy_data)
        logger.info(f"Loaded {len(self.legacy_data)} Legacy records")
    
    def clean_email(self, email):
        """Clean and normalize email addresses"""
        if pd.isna(email):
            return ""
        return str(email).lower().strip()
    
    def clean_name(self, name):
        """Clean and normalize names"""
        if pd.isna(name):
            return ""
        # Remove extra spaces, normalize case
        name = re.sub(r'\s+', ' ', str(name).strip())
        # Convert to title case for consistency
        return name.title()
    
    def normalize_phone(self, phone):
        """Normalize phone numbers"""
        if pd.isna(phone):
            return ""
        # Remove all non-digit characters
        digits_only = re.sub(r'\D', '', str(phone))
        # Add formatting if it's a 10-digit US number
        if len(digits_only) == 10:
            return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
        elif len(digits_only) == 11 and digits_only.startswith('1'):
            return f"({digits_only[1:4]}) {digits_only[4:7]}-{digits_only[7:]}"
        return phone
    
    def similarity(self, a, b):
        """Calculate similarity between two strings"""
        if pd.isna(a) or pd.isna(b):
            return 0.0
        return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()
    
    def prepare_data(self):
        """Clean and prepare both datasets for merging"""
        logger.info("Preparing WordPress data...")
        
        # Clean WordPress data
        wp = self.wordpress_data.copy()
        wp['email_clean'] = wp['email'].apply(self.clean_email)
        wp['first_name_clean'] = wp['first_name'].apply(self.clean_name)
        wp['last_name_clean'] = wp['last_name'].apply(self.clean_name)
        wp['full_name_clean'] = wp['first_name_clean'] + ' ' + wp['last_name_clean']
        
        # Use mepr_ fields as primary if available, fall back to main fields
        wp['mepr_email_clean'] = wp['mepr_email'].apply(self.clean_email)
        wp['mepr_first_name_clean'] = wp['mepr_first_name'].apply(self.clean_name)
        wp['mepr_last_name_clean'] = wp['mepr_last_name'].apply(self.clean_name)
        wp['mepr_full_name_clean'] = wp['mepr_first_name_clean'] + ' ' + wp['mepr_last_name_clean']
        
        # Combine email fields (prefer mepr_email if available)
        wp['best_email'] = wp['mepr_email_clean'].fillna(wp['email_clean'])
        wp['best_first_name'] = wp['mepr_first_name_clean'].fillna(wp['first_name_clean'])
        wp['best_last_name'] = wp['mepr_last_name_clean'].fillna(wp['last_name_clean'])
        wp['best_full_name'] = wp['best_first_name'] + ' ' + wp['best_last_name']
        
        logger.info("Preparing Legacy data...")
        
        # Clean Legacy data
        legacy = self.legacy_data.copy()
        legacy['email_clean'] = legacy['E-mail'].apply(self.clean_email)
        legacy['first_name_clean'] = legacy['fname'].apply(self.clean_name)
        legacy['last_name_clean'] = legacy['lname'].apply(self.clean_name)
        legacy['full_name_clean'] = legacy['first_name_clean'] + ' ' + legacy['last_name_clean']
        legacy['phone_clean'] = legacy['Phone'].apply(self.normalize_phone)
        
        self.wordpress_data = wp
        self.legacy_data = legacy
        
        logger.info("Data preparation complete")
    
    def find_email_matches(self):
        """Find matches based on email addresses"""
        logger.info("Finding email-based matches...")
        
        email_matches = []
        wp_emails = set(self.wordpress_data['best_email'].dropna())
        
        for idx, legacy_row in self.legacy_data.iterrows():
            legacy_email = legacy_row['email_clean']
            if legacy_email and legacy_email in wp_emails:
                wp_match = self.wordpress_data[self.wordpress_data['best_email'] == legacy_email]
                if len(wp_match) == 1:  # Exact single match
                    email_matches.append({
                        'wp_index': wp_match.index[0],
                        'legacy_index': idx,
                        'match_type': 'email_exact',
                        'confidence': 1.0,
                        'match_field': legacy_email
                    })
        
        self.merge_stats['email_matches'] = len(email_matches)
        logger.info(f"Found {len(email_matches)} email-based matches")
        return email_matches
    
    def find_name_matches(self, email_matches):
        """Find matches based on name similarity (excluding email matches)"""
        logger.info("Finding name-based matches...")
        
        # Get indices of already matched records
        matched_wp_indices = {match['wp_index'] for match in email_matches}
        matched_legacy_indices = {match['legacy_index'] for match in email_matches}
        
        name_matches = []
        
        # Get unmatched records
        unmatched_wp = self.wordpress_data[~self.wordpress_data.index.isin(matched_wp_indices)]
        unmatched_legacy = self.legacy_data[~self.legacy_data.index.isin(matched_legacy_indices)]
        
        for legacy_idx, legacy_row in unmatched_legacy.iterrows():
            legacy_name = legacy_row['full_name_clean']
            if not legacy_name.strip():
                continue
                
            best_match = None
            best_score = 0.0
            
            for wp_idx, wp_row in unmatched_wp.iterrows():
                wp_name = wp_row['best_full_name']
                if not wp_name.strip():
                    continue
                    
                score = self.similarity(legacy_name, wp_name)
                
                # Also check individual name components
                first_score = self.similarity(legacy_row['first_name_clean'], wp_row['best_first_name'])
                last_score = self.similarity(legacy_row['last_name_clean'], wp_row['best_last_name'])
                
                # Combined score with emphasis on exact last name matches
                combined_score = (score * 0.6) + (first_score * 0.2) + (last_score * 0.2)
                if last_score > 0.9:  # Boost for exact last name matches
                    combined_score += 0.1
                
                if combined_score > best_score and combined_score > 0.8:  # High threshold
                    best_score = combined_score
                    best_match = {
                        'wp_index': wp_idx,
                        'legacy_index': legacy_idx,
                        'match_type': 'name_similarity',
                        'confidence': combined_score,
                        'match_field': f"{legacy_name} -> {wp_name}"
                    }
            
            if best_match:
                name_matches.append(best_match)
                # Remove from unmatched to avoid duplicate matches
                unmatched_wp = unmatched_wp[unmatched_wp.index != best_match['wp_index']]
        
        self.merge_stats['name_matches'] = len(name_matches)
        logger.info(f"Found {len(name_matches)} name-based matches")
        return name_matches
    
    def create_merged_dataset(self, email_matches, name_matches):
        """Create the final merged dataset"""
        logger.info("Creating merged dataset...")
        
        all_matches = email_matches + name_matches
        
        # Start with WordPress data as base
        merged = self.wordpress_data.copy()
        
        # Add columns for legacy data
        legacy_columns = {
            'legacy_id': 'ID',
            'legacy_title': 'Title',
            'legacy_phd_year': 'PhD Year',
            'legacy_affiliation': 'Affiliation',
            'legacy_affiliation_type': 'Affiliation Type',
            'legacy_phone': 'phone_clean',
            'legacy_address_1': 'address_1',
            'legacy_address_2': 'adress_2',  # Note: typo in original
            'legacy_city': 'city',
            'legacy_state': 'state',
            'legacy_zip': 'zip',
            'legacy_country': 'country',
            'legacy_address_label': 'address_label'
        }
        
        # Initialize legacy columns
        for new_col in legacy_columns.keys():
            merged[new_col] = None
        
        # Add match metadata
        merged['legacy_match_type'] = None
        merged['legacy_match_confidence'] = None
        merged['data_source'] = 'wordpress'
        
        # Fill in legacy data for matches
        enriched_count = 0
        for match in all_matches:
            wp_idx = match['wp_index']
            legacy_idx = match['legacy_index']
            legacy_row = self.legacy_data.loc[legacy_idx]
            
            for new_col, legacy_col in legacy_columns.items():
                merged.loc[wp_idx, new_col] = legacy_row[legacy_col]
            
            merged.loc[wp_idx, 'legacy_match_type'] = match['match_type']
            merged.loc[wp_idx, 'legacy_match_confidence'] = match['confidence']
            merged.loc[wp_idx, 'data_source'] = 'merged'
            enriched_count += 1
        
        # Add unmatched legacy records
        matched_legacy_indices = {match['legacy_index'] for match in all_matches}
        unmatched_legacy = self.legacy_data[~self.legacy_data.index.isin(matched_legacy_indices)]
        
        legacy_only_records = []
        for idx, legacy_row in unmatched_legacy.iterrows():
            record = {col: None for col in merged.columns}
            
            # Fill basic fields
            record['email'] = legacy_row['E-mail']
            record['first_name'] = legacy_row['fname']
            record['last_name'] = legacy_row['lname']
            record['name'] = f"{legacy_row['fname']} {legacy_row['lname']}"
            
            # Fill legacy fields
            for new_col, legacy_col in legacy_columns.items():
                record[new_col] = legacy_row[legacy_col]
            
            record['data_source'] = 'legacy_only'
            record['status'] = 'inactive'  # Assume inactive since not in WordPress
            
            legacy_only_records.append(record)
        
        if legacy_only_records:
            legacy_df = pd.DataFrame(legacy_only_records)
            merged = pd.concat([merged, legacy_df], ignore_index=True)
        
        self.merge_stats['enriched_records'] = enriched_count
        self.merge_stats['legacy_only'] = len(legacy_only_records)
        self.merge_stats['wordpress_only'] = len(merged[merged['data_source'] == 'wordpress'])
        
        self.merged_data = merged
        logger.info(f"Merged dataset created with {len(merged)} total records")
        
        return merged
    
    def generate_report(self):
        """Generate merge statistics report"""
        report = f"""
APS Membership Data Merge Report
==============================

Data Sources:
- WordPress Export: {self.merge_stats['total_wordpress']} records
- Legacy Excel: {self.merge_stats['total_legacy']} records

Merge Results:
- Email-based matches: {self.merge_stats['email_matches']}
- Name-based matches: {self.merge_stats['name_matches']}
- Total enriched WordPress records: {self.merge_stats['enriched_records']}
- WordPress-only records: {self.merge_stats['wordpress_only']}
- Legacy-only records: {self.merge_stats['legacy_only']}

Data Quality Insights:
- Match rate: {((self.merge_stats['email_matches'] + self.merge_stats['name_matches']) / self.merge_stats['total_legacy'] * 100):.1f}%
- Enrichment rate: {(self.merge_stats['enriched_records'] / self.merge_stats['total_wordpress'] * 100):.1f}%

Recommended Next Steps:
1. Review name-based matches with confidence < 0.9 for accuracy
2. Implement re-engagement campaign for legacy-only members
3. Update membership forms to capture PhD year and affiliation type
4. Consider manual review of high-value unmatched legacy records
        """
        return report
    
    def save_results(self, output_dir):
        """Save merged data and reports"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Save merged data
        merged_file = output_path / 'aps_members_merged.csv'
        self.merged_data.to_csv(merged_file, index=False)
        logger.info(f"Merged data saved to {merged_file}")
        
        # Save report
        report_file = output_path / 'merge_report.txt'
        with open(report_file, 'w') as f:
            f.write(self.generate_report())
        logger.info(f"Merge report saved to {report_file}")
        
        # Save match details for review
        matches_data = []
        if hasattr(self, '_all_matches'):
            for match in self._all_matches:
                wp_row = self.wordpress_data.loc[match['wp_index']]
                legacy_row = self.legacy_data.loc[match['legacy_index']]
                matches_data.append({
                    'match_type': match['match_type'],
                    'confidence': match['confidence'],
                    'wp_name': wp_row['best_full_name'],
                    'wp_email': wp_row['best_email'],
                    'legacy_name': legacy_row['full_name_clean'],
                    'legacy_email': legacy_row['email_clean'],
                    'legacy_phd_year': legacy_row['PhD Year'],
                    'legacy_affiliation': legacy_row['Affiliation']
                })
        
        if matches_data:
            matches_df = pd.DataFrame(matches_data)
            matches_file = output_path / 'match_details.csv'
            matches_df.to_csv(matches_file, index=False)
            logger.info(f"Match details saved to {matches_file}")
        
        return merged_file
    
    def run_merge(self, output_dir='members'):
        """Execute the complete merge process"""
        logger.info("Starting APS membership data merge...")
        
        # Load and prepare data
        self.load_data()
        self.prepare_data()
        
        # Find matches
        email_matches = self.find_email_matches()
        name_matches = self.find_name_matches(email_matches)
        self._all_matches = email_matches + name_matches
        
        # Create merged dataset
        merged_data = self.create_merged_dataset(email_matches, name_matches)
        
        # Save results
        output_file = self.save_results(output_dir)
        
        # Print report
        print(self.generate_report())
        
        logger.info("Merge process completed successfully!")
        return output_file, self.merged_data

def main():
    """Main execution function"""
    # File paths
    csv_file = 'members/members-1752942440.csv'
    excel_file = 'members/members_merged_1.0.xlsx'
    
    # Create merger and run
    merger = MembershipDataMerger(csv_file, excel_file)
    output_file, merged_data = merger.run_merge()
    
    print(f"\nMerge completed! Output saved to: {output_file}")
    print(f"Total records in merged dataset: {len(merged_data)}")

if __name__ == "__main__":
    main()