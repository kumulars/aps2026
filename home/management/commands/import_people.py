from django.core.management.base import BaseCommand
from home.models import Person
import csv
import os

class Command(BaseCommand):
    help = "Import People from CSV"

    def handle(self, *args, **kwargs):
        csv_path = os.path.join("import_files", "clean_people_import.csv")
        created_count = 0

        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                person, created = Person.objects.get_or_create(
                    first_name=row["first_name"].strip(),
                    last_name=row["last_name"].strip(),
                    defaults={
                        "category": row["category"].strip(),
                        "professional_title": row["professional_title"].strip(),
                        "institution": row["institution"].strip(),
                        "service_start_date": row["service_start_date"] or None,
                        "service_end_date": row["service_end_date"] or None,
                    }
                )
                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Imported {created_count} people"))
