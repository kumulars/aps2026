# Email Configuration Setup Guide

This guide will help you configure email settings for the PeptideLinks automation system.

## Quick Setup (Recommended for Testing)

### 1. Create Local Settings File

Copy the template and customize:

```bash
cp aps2026_site/settings/local.py.template aps2026_site/settings/local.py
```

### 2. Configure Gmail (Easiest Option)

Edit `aps2026_site/settings/local.py`:

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate an App Password**:
   - Go to Google Account settings
   - Security → 2-Step Verification → App passwords
   - Create password for "Mail" 
   - Copy the 16-character password

3. **Update local.py**:
```python
EMAIL_HOST_USER = 'your-gmail@gmail.com'          # Your Gmail address
EMAIL_HOST_PASSWORD = 'abcd efgh ijkl mnop'       # Your 16-char app password
ADMINS = [
    ('Your Name', 'your-gmail@gmail.com'),         # Your email for reports
]
```

### 3. Test Email Configuration

```bash
# Test basic email sending
python manage.py sendtestemail your-email@gmail.com

# Test automation email report
python manage.py automated_peptidelinks_updater --dry-run --email-report
```

## Production Setup

### Option 1: Gmail (Simple)
Use the same Gmail setup as above, but in production settings.

### Option 2: Professional SMTP Service

**SendGrid** (recommended for high volume):
```python
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = 'your-sendgrid-api-key'
```

**Mailgun**:
```python
EMAIL_HOST = 'smtp.mailgun.org'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-mailgun-username'
EMAIL_HOST_PASSWORD = 'your-mailgun-password'
```

## Email Settings Reference

### Current Configuration Files:

- `aps2026_site/settings/base.py` - Default settings with console backend
- `aps2026_site/settings/production.py` - Production overrides (commented out)
- `aps2026_site/settings/local.py` - Your local overrides (create from template)

### Key Settings:

```python
# Email backend (choose one)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'          # Real emails
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'       # Print to console
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'     # Save to files

# SMTP Configuration
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@domain.com'
EMAIL_HOST_PASSWORD = 'your-password-or-app-password'
DEFAULT_FROM_EMAIL = 'APS 2026 <noreply@americanpeptidesociety.org>'

# Recipients for automation reports
ADMINS = [
    ('Your Name', 'your-email@domain.com'),
]
```

## Automation Emails

The system sends these types of emails:

### 1. **Automation Reports** (weekly/monthly)
- Update statistics
- New/updated researchers count  
- Unicode fixes applied
- Broken links found
- Sent to `ADMINS`

### 2. **Researcher Profile Claims**
- When researchers claim their profiles
- Includes verification details
- Sent to `ADMINS`

### 3. **Profile Update Requests**
- When researchers request updates
- Includes requested changes
- Sent to `ADMINS`

### 4. **Confirmation Emails**
- Sent to researchers after claims/updates
- Confirms receipt of their request

## Testing Email Setup

### 1. Test Django Email (Basic)
```bash
python manage.py shell
```
```python
from django.core.mail import send_mail
send_mail(
    'Test Email',
    'This is a test from APS Django.',
    'from@example.com',
    ['your-email@gmail.com'],
    fail_silently=False,
)
```

### 2. Test Automation Email Report
```bash
python manage.py automated_peptidelinks_updater --dry-run --email-report
```

### 3. Test Profile Claim API
Visit your site and test the researcher profile claim form on the PeptideLinks page.

## Troubleshooting

### Common Issues:

1. **Gmail "Less Secure Apps" Error**
   - Solution: Use App Passwords instead (see setup above)

2. **Connection Timeout**
   - Check EMAIL_HOST and EMAIL_PORT
   - Verify firewall/network settings

3. **Authentication Failed**
   - Double-check EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
   - For Gmail, ensure 2FA is enabled and you're using App Password

4. **Emails Not Sending**
   - Check ADMINS list is properly formatted
   - Verify DEFAULT_FROM_EMAIL is set
   - Check Django logs for error messages

### Debug Mode:
Add to your local.py for detailed email debugging:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'loggers': {
        'django.core.mail': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

## Security Notes

- Never commit email passwords to Git
- Use App Passwords for Gmail (never your main password)  
- Consider using environment variables for sensitive data
- Use professional SMTP services for production (SendGrid, Mailgun, etc.)

## Support

If you need help:
1. Check the Django logs in `logs/peptidelinks_automation.log`
2. Test with console backend first to verify email content
3. Gradually move to file backend, then SMTP backend