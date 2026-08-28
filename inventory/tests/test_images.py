from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from inventory.models import Item, Photo

pytestmark = pytest.mark.django_db


def make_item(entities):
    p, c, u = entities
    return Item.objects.create(name="X", person=p, category=c, storage_unit=u, primary_color="Mavi")


def test_resize_ratio_thumbnail_and_webp(entities, image_upload):
    photo = Photo.objects.create(item=make_item(entities), image=image_upload((3200, 1600)))
    with Image.open(photo.image) as im:
        assert im.size == (1600, 800) and im.format == "WEBP"
    with Image.open(photo.thumbnail) as thumb:
        assert max(thumb.size) == 400
    assert photo.image.name.endswith(".webp") and "photo.jpg" not in photo.image.name


def test_exif_orientation(entities):
    exif = Image.Exif()
    exif[274] = 6
    data = BytesIO()
    Image.new("RGB", (1200, 600)).save(data, "JPEG", exif=exif)
    upload = SimpleUploadedFile("oriented.jpg", data.getvalue(), content_type="image/jpeg")
    photo = Photo.objects.create(item=make_item(entities), image=upload)
    with Image.open(photo.image) as im:
        assert im.height > im.width


def test_bad_file_rejected_without_record(entities):
    upload = SimpleUploadedFile("bad.jpg", b"not an image", content_type="image/jpeg")
    with pytest.raises(ValidationError):
        Photo.objects.create(item=make_item(entities), image=upload)
    assert Photo.objects.count() == 0
