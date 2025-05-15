import csv
from django.db.models import Value, functions, Max
from django.db import models
from home.models import Person, Obituary
from wagtail.images.models import Image

def import_obituaries():
    path = "import_files/obituaries.csv"

    # Determine current max obit_id
    current_max_id = Obituary.objects.aggregate(Max("obituary_id"))["obituary_id__max"] or 0
    next_id = current_max_id + 1

    with open(path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            first_name = row["obit_first_name"].strip()
            last_name = row["obit_last_name"].strip()
            blurb = row.get("obit_blurb", "").strip()
            full_text = row.get("obit_full_text", "").strip()

            try:
                person = Person.objects.get(first_name__iexact=first_name, last_name__iexact=last_name)
            except Person.DoesNotExist:
                # Try fallback using combined name match
                full_guess = f"{first_name} {last_name}"
                matches = Person.objects.annotate(
                    full_name=functions.Concat('first_name', Value(' '), 'last_name')
                ).filter(full_name__icontains=full_guess)

                if matches.exists():
                    person = matches.first()
                    print(f"⚠️ Fallback matched: {full_guess} → {person.first_name} {person.last_name}")
                else:
                    print(f"❌ Person not found: {first_name} {last_name}")
                    continue

            # No image matching in current import
            image = None

            Obituary.objects.update_or_create(
                person=person,
                defaults={
                    "obituary_id": next_id,
                    "blurb": blurb,
                    "full_text": full_text,
                    "image": image,
                }
            )
            print(f"✅ Imported obituary #{next_id} → {person.first_name} {person.last_name}")
            next_id += 1

# Execute the import
import_obituaries()
