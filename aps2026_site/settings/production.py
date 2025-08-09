from .base import *

DEBUG = False

# ===============================================
# Production Email Configuration
# ===============================================

# SMTP Email Backend (uncomment and configure for production)
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Gmail Configuration (recommended)
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-aps-email@gmail.com'
# EMAIL_HOST_PASSWORD = 'your-app-password'  # Generate app password in Gmail
# DEFAULT_FROM_EMAIL = 'APS 2026 <noreply@americanpeptidesociety.org>'

# Alternative: Other SMTP providers
# EMAIL_HOST = 'smtp.sendgrid.net'  # SendGrid
# EMAIL_HOST = 'smtp.mailgun.org'   # Mailgun
# EMAIL_HOST = 'smtp.zoho.com'      # Zoho
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'your-smtp-username'
# EMAIL_HOST_PASSWORD = 'your-smtp-password'

# Production administrators (update with real email addresses)
ADMINS = [
    ('APS Admin', 'admin@americanpeptidesociety.org'),
    ('Site Administrator', 'webmaster@americanpeptidesociety.org'),
    # Add your email here:
    # ('Your Name', 'your-email@domain.com'),
]

MANAGERS = ADMINS

# Security settings for production email
EMAIL_USE_LOCALTIME = False
EMAIL_TIMEOUT = 10

try:
    from .local import *
except ImportError:
    pass
