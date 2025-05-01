from wagtail.images.models import Image

updated = 0

for image in Image.objects.all():
    # Only update if the title is empty or identical to the filename (without extension)
    base_filename = image.file.name.split("/")[-1].rsplit(".", 1)[0]

    if not image.title.strip() or image.title.strip().lower() == base_filename.lower():
        image.title = "News Research Image"
        image.save()
        updated += 1

print(f"✅ Updated {updated} image titles.")
