import pytest
from django.db import IntegrityError
from inventory.models import Item, Photo, Tag
pytestmark = pytest.mark.django_db

def item(entities):
    p, c, u = entities
    return Item.objects.create(name="Mont", person=p, category=c, storage_unit=u, primary_color="Siyah")
def test_first_photo_is_cover_and_only_one(entities, image_upload):
    obj = item(entities); first = Photo.objects.create(item=obj, image=image_upload()); second = Photo.objects.create(item=obj, image=image_upload(name="b.jpg"))
    assert first.is_cover and not second.is_cover
    second.set_as_cover(); first.refresh_from_db(); assert second.is_cover and not first.is_cover
    with pytest.raises(IntegrityError):
        Photo.objects.filter(pk=first.pk).update(is_cover=True)
def test_storage_relation_and_tags(entities):
    obj = item(entities); tag = Tag.objects.create(name="Favori"); obj.tags.add(tag)
    assert list(entities[2].items.all()) == [obj] and list(tag.items.all()) == [obj]
def test_archive_excluded(entities):
    obj = item(entities); obj.archive()
    assert not Item.objects.visible().filter(pk=obj.pk).exists()
