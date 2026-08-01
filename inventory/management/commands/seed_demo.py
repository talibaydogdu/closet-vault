from io import BytesIO
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw
from inventory.models import Category, Item, Person, Photo, StorageUnit, Tag

class Command(BaseCommand):
    help = "Tekrarlanabilir demo verisi oluşturur"
    def handle(self, *args, **options):
        people = {name: Person.objects.get_or_create(name=name)[0] for name in ["Ben", "Eşim", "Ortak"]}
        units_data = [("Vakum Poşeti 1", "VACUUM_BAG", "Yatak odası dolabı, üst raf"), ("Vakum Poşeti 2", "VACUUM_BAG", "Balkon dolabı, orta raf"), ("Vakum Poşeti 3", "VACUUM_BAG", "Yatak odası dolabı, ikinci raf"), ("Büyük Siyah Valiz", "SUITCASE", "Misafir odası dolabı"), ("Yatak Odası Dolabı 2. Raf", "SHELF", "Yatak odası dolabı, ikinci raf")]
        units = {name: StorageUnit.objects.get_or_create(name=name, defaults={"unit_type": kind, "location_text": location})[0] for name, kind, location in units_data}
        roots = {}
        for root, children in {"Üst Giyim": ["Tişört", "Gömlek", "Kazak", "Sweatshirt"], "Alt Giyim": ["Pantolon", "Jean", "Şort"], "Dış Giyim": ["Mont", "Ceket", "Kaban"], "Ayakkabı": [], "Aksesuar": ["Çanta", "Saat", "Gözlük", "Kemer", "Takı"]}.items():
            parent, _ = Category.objects.get_or_create(name=root, parent=None); roots[root] = parent
            for child in children: Category.objects.get_or_create(name=child, parent=parent)
        favorite, _ = Tag.objects.get_or_create(name="Favori")
        examples = [("Siyah kışlık mont", "Ben", "Mont", "Vakum Poşeti 3", "Siyah"), ("Mavi gömlek", "Eşim", "Gömlek", "Yatak Odası Dolabı 2. Raf", "Mavi"), ("Kahverengi seyahat çantası", "Ortak", "Çanta", "Büyük Siyah Valiz", "Kahverengi")]
        for index, (name, person, category, unit, color) in enumerate(examples):
            cat = Category.objects.get(name=category)
            item, created = Item.objects.get_or_create(name=name, defaults={"person": people[person], "category": cat, "storage_unit": units[unit], "primary_color": color, "brand": "Demo"})
            if created:
                item.tags.add(favorite)
                image = Image.new("RGB", (900, 1200), ["#222222", "#3976b5", "#9b6b43"][index]); draw = ImageDraw.Draw(image); draw.text((80, 100), name, fill="white")
                data = BytesIO(); image.save(data, "JPEG"); Photo.objects.create(item=item, image=ContentFile(data.getvalue(), name=f"demo-{index}.jpg"))
        self.stdout.write(self.style.SUCCESS("Demo verileri hazır."))
