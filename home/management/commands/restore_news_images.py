from django.core.management.base import BaseCommand
from wagtail.images.models import Image
from home.models import NewsResearchItem


class Command(BaseCommand):
    help = 'Restore image associations for news items'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get all news images
        news_images = Image.objects.filter(title__icontains='News Research Image').order_by('id')
        self.stdout.write(f"Found {news_images.count()} news images")
        
        # Get news items that need images (excluding the 14 new ones)
        news_items_needing_images = NewsResearchItem.objects.filter(
            news_item_image__isnull=True
        ).exclude(
            news_item_id__in=[
                'import-conjugation-chemistry',
                'import-grafted-coiled-coils',
                'import-efficient-sirna-delivery',
                'import-potent-antifungal-lipopeptide',
                'import-oxidative-peptide-coupling',
                'import-quorum-sensing-redux',
                'import-macrocyclic-peptide-antibiotics',
                'import-rational-design',
                'import-intracellular-targeting',
                'import-shaping-peptide-assemblies',
                'import-delivery-of-peptide-lytac',
                'import-peptide-anti-obesity-20',
                'import-conformational-equilibrium',
                'import-proline-scanning'
            ]
        ).order_by('created_at')
        
        self.stdout.write(f"Found {news_items_needing_images.count()} news items needing images")
        
        if dry_run:
            self.stdout.write("\n🔍 DRY RUN - Would make these associations:")
        
        # Match images to news items
        matched = 0
        for i, (news_item, image) in enumerate(zip(news_items_needing_images, news_images)):
            if dry_run:
                self.stdout.write(
                    f"  {i+1}. '{news_item.news_item_short_title[:50]}...' → Image ID {image.id}"
                )
            else:
                news_item.news_item_image = image
                news_item.save()
                matched += 1
                if matched % 10 == 0:
                    self.stdout.write(f"  Processed {matched} items...")
        
        if dry_run:
            self.stdout.write(f"\n Would assign {min(news_images.count(), news_items_needing_images.count())} images")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Successfully restored {matched} image associations"
                )
            )
            
            # Final check
            total_with_images = NewsResearchItem.objects.exclude(news_item_image__isnull=True).count()
            self.stdout.write(f"📊 Total news items with images: {total_with_images}")