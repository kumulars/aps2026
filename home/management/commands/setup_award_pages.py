"""
Management command to create award pages in Wagtail CMS.
"""

from django.core.management.base import BaseCommand
from home.models import HomePage, AwardsIndexPage, AwardTypePage, AwardType


class Command(BaseCommand):
    """Management command to create award pages."""
    
    help = 'Create award pages in Wagtail CMS'
    
    def handle(self, *args, **options):
        """Execute the command."""
        
        try:
            # Get the homepage
            homepage = HomePage.objects.first()
            if not homepage:
                self.stdout.write(self.style.ERROR("No homepage found!"))
                return
            
            self.stdout.write(f"Found homepage: {homepage.title}")
            
            # Create Awards Index Page
            awards_index = None
            try:
                awards_index = AwardsIndexPage.objects.get(slug='awards')
                self.stdout.write(f"✓ Awards Index Page already exists: {awards_index.title}")
            except AwardsIndexPage.DoesNotExist:
                awards_index = AwardsIndexPage(
                    title='Awards',
                    slug='awards',
                    introduction='''<p>The American Peptide Society recognizes outstanding contributions to peptide science through our prestigious awards program. Since 1977, we have honored researchers who have advanced the field through groundbreaking research, exceptional mentorship, and dedication to scientific excellence.</p><p>Our awards celebrate achievements across the spectrum of peptide science, from fundamental research to practical applications, recognizing both established leaders and emerging talent in the field.</p>''',
                )
                homepage.add_child(instance=awards_index)
                awards_index.save_revision().publish()
                self.stdout.write(self.style.SUCCESS(f"✓ Created Awards Index Page: {awards_index.title}"))
            
            # Create individual award type pages
            award_types = AwardType.objects.all().order_by('display_order')
            
            for award_type in award_types:
                page_slug = f"{award_type.slug}-award"
                page_title = award_type.name
                
                try:
                    award_page = AwardTypePage.objects.get(award_type=award_type)
                    self.stdout.write(f"✓ Award Type Page already exists: {page_title}")
                except AwardTypePage.DoesNotExist:
                    award_page = AwardTypePage(
                        title=page_title,
                        slug=page_slug,
                        award_type=award_type,
                        nomination_info=f'''<h4>Nomination Process</h4><p>Nominations for the {award_type.name} are accepted annually. Please contact the American Peptide Society for detailed nomination guidelines and deadlines.</p><p><strong>Contact:</strong> <a href="mailto:aps@americanpeptidesociety.org">aps@americanpeptidesociety.org</a></p>''',
                    )
                    awards_index.add_child(instance=award_page)
                    award_page.save_revision().publish()
                    self.stdout.write(self.style.SUCCESS(f"✓ Created Award Type Page: {page_title}"))
            
            self.stdout.write(self.style.SUCCESS("\n🎉 Award pages setup complete!"))
            self.stdout.write(f"📍 Awards Index URL: /awards/")
            
            for award_type in award_types:
                page_slug = f"{award_type.slug}-award"
                self.stdout.write(f"📍 {award_type.name} URL: /awards/{page_slug}/")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))
            import traceback
            traceback.print_exc()