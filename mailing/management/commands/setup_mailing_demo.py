from django.core.management.base import BaseCommand
from mailing.models import EmailTemplate, MailingList, Subscriber


class Command(BaseCommand):
    help = 'Set up demo data for the mailing system'

    def handle(self, *args, **options):
        # Create a sample email template
        template, created = EmailTemplate.objects.get_or_create(
            name="Welcome Newsletter Template",
            defaults={
                'subject': "Welcome to the American Peptide Society Newsletter, {{first_name}}!",
                'template_type': "welcome",
                'html_content': """
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .header { background: #2c5aa0; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .footer { background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; }
        .btn { background: #2c5aa0; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; display: inline-block; }
    </style>
</head>
<body>
    <div class="header">
        <h1>American Peptide Society</h1>
        <p>Advancing Peptide Science Worldwide</p>
    </div>
    
    <div class="content">
        <h2>Welcome {{first_name}}!</h2>
        
        <p>Thank you for subscribing to the American Peptide Society newsletter! We're excited to have you join our community of researchers, scientists, and peptide enthusiasts.</p>
        
        <p>In our newsletters, you'll receive:</p>
        <ul>
            <li>Latest peptide research and publications</li>
            <li>Upcoming symposium and conference announcements</li>
            <li>Award and fellowship opportunities</li>
            <li>Member spotlight features</li>
            <li>Industry news and developments</li>
        </ul>
        
        <p style="text-align: center; margin: 30px 0;">
            <a href="https://americanpeptidesociety.org/people/" class="btn">Browse Research Directory</a>
        </p>
        
        <p>Stay connected with the peptide community!</p>
        
        <p>Best regards,<br>The APS Team</p>
    </div>
    
    <div class="footer">
        <p>American Peptide Society | {{current_year}}</p>
        <p>You received this email because you subscribed to our newsletter.</p>
        <p><a href="{{unsubscribe_link}}">Unsubscribe</a> if you no longer wish to receive these emails.</p>
    </div>
</body>
</html>
                """,
                'text_content': """
Welcome to the American Peptide Society Newsletter, {{first_name}}!

Thank you for subscribing to the American Peptide Society newsletter! We're excited to have you join our community of researchers, scientists, and peptide enthusiasts.

In our newsletters, you'll receive:
- Latest peptide research and publications
- Upcoming symposium and conference announcements  
- Award and fellowship opportunities
- Member spotlight features
- Industry news and developments

Visit our research directory: https://americanpeptidesociety.org/people/

Stay connected with the peptide community!

Best regards,
The APS Team

---
American Peptide Society | {{current_year}}
You received this email because you subscribed to our newsletter.
Unsubscribe: {{unsubscribe_link}}
                """
            }
        )
        
        if created:
            self.stdout.write(f"Created email template: {template.name}")
        else:
            self.stdout.write(f"Email template already exists: {template.name}")

        # Create mailing lists
        lists_data = [
            ("All Subscribers", "All newsletter subscribers", "all"),
            ("APS Members", "APS society members only", "members"),
            ("Researchers", "Active peptide researchers", "researchers"),
            ("Symposium Attendees", "People who attended APS symposiums", "symposium"),
        ]
        
        for name, description, list_type in lists_data:
            mailing_list, created = MailingList.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'list_type': list_type
                }
            )
            if created:
                self.stdout.write(f"Created mailing list: {name}")
            else:
                self.stdout.write(f"Mailing list already exists: {name}")

        self.stdout.write(
            self.style.SUCCESS(
                f'Setup complete! Created {EmailTemplate.objects.count()} templates and {MailingList.objects.count()} mailing lists.'
            )
        )