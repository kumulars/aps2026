"""
Setup automation for PeptideLinks updates using Django-cron
"""

from django.core.management.base import BaseCommand
from django.conf import settings
import os


class Command(BaseCommand):
    help = 'Setup automated PeptideLinks updates'

    def handle(self, *args, **options):
        self.stdout.write("⚙️ Setting up PeptideLinks automation...")
        
        # Create cron job entries
        cron_jobs = """
# PeptideLinks Automation Jobs
# Weekly full update (Sundays at 2 AM)
0 2 * * 0 cd {project_path} && python manage.py automated_peptidelinks_updater --check-links --email-report

# Daily quick update check (weekdays at 6 AM) 
0 6 * * 1-5 cd {project_path} && python manage.py automated_peptidelinks_updater

# Monthly comprehensive update (1st of month at 3 AM)
0 3 1 * * cd {project_path} && python manage.py automated_peptidelinks_updater --force-update --check-links --email-report
""".format(project_path=settings.BASE_DIR)

        self.stdout.write("\n📋 Suggested cron jobs:")
        self.stdout.write(cron_jobs)
        
        # Create automation settings
        automation_settings = """
# Add these to your settings.py for email notifications

# Email settings for automation reports
ADMINS = [
    ('Your Name', 'your-email@domain.com'),
]

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your-smtp-server.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@domain.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'noreply@americanpeptidesociety.org'

# Logging for automation
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'peptidelinks_automation.log'),
        },
    },
    'loggers': {
        'home.management.commands.automated_peptidelinks_updater': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
"""
        
        self.stdout.write("\n⚙️ Suggested settings.py additions:")
        self.stdout.write(automation_settings)
        
        # Create logs directory if it doesn't exist
        logs_dir = os.path.join(settings.BASE_DIR, 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            self.stdout.write(f"📁 Created logs directory: {logs_dir}")
        
        self.stdout.write("\n✅ Automation setup complete!")
        self.stdout.write("\nNext steps:")
        self.stdout.write("1. Add the cron jobs to your server's crontab")
        self.stdout.write("2. Add email settings to your settings.py")  
        self.stdout.write("3. Test with: python manage.py automated_peptidelinks_updater --dry-run")