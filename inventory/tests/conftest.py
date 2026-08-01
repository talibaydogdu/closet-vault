from io import BytesIO
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from inventory.models import Category, Person, StorageUnit

@pytest.fixture
def image_upload():
    def make(size=(800, 600), name="photo.jpg", exif=None):
        data = BytesIO(); Image.new("RGB", size, "red").save(data, "JPEG", exif=exif)
        return SimpleUploadedFile(name, data.getvalue(), content_type="image/jpeg")
    return make
@pytest.fixture
def entities(db):
    person = Person.objects.create(name="Ben")
    category = Category.objects.create(name="Mont")
    unit = StorageUnit.objects.create(name="Poşet 1", unit_type="VACUUM_BAG", location_text="Dolap")
    return person, category, unit
