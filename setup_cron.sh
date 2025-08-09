#!/bin/bash
# Setup script for PeptideLinks automation cron jobs

echo "Setting up PeptideLinks automation cron jobs..."

# Get the current directory (project path)
PROJECT_PATH=$(pwd)
echo "Project path: $PROJECT_PATH"

# Create the cron entries
CRON_ENTRIES="
# PeptideLinks Automation Jobs - Added $(date)
# Weekly full update (Sundays at 2 AM)
0 2 * * 0 cd $PROJECT_PATH && source venv/bin/activate && python manage.py automated_peptidelinks_updater --check-links --email-report

# Daily quick update check (weekdays at 6 AM) 
0 6 * * 1-5 cd $PROJECT_PATH && source venv/bin/activate && python manage.py automated_peptidelinks_updater

# Monthly comprehensive update (1st of month at 3 AM)
0 3 1 * * cd $PROJECT_PATH && source venv/bin/activate && python manage.py automated_peptidelinks_updater --force-update --check-links --email-report
"

# Save current crontab
echo "Backing up current crontab..."
crontab -l > crontab_backup_$(date +%Y%m%d_%H%M%S).txt 2>/dev/null || echo "No existing crontab found"

# Add new entries to crontab
echo "Adding PeptideLinks automation jobs to crontab..."
(crontab -l 2>/dev/null; echo "$CRON_ENTRIES") | crontab -

echo "✅ Cron jobs added successfully!"
echo ""
echo "To verify the cron jobs were added, run:"
echo "crontab -l"
echo ""
echo "To remove these jobs later, run:"
echo "crontab -e"
echo "and delete the PeptideLinks entries"