import pytest
from django.urls import reverse

from inventory.models import Item, StorageUnit

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def login(client, django_user_model):
    client.force_login(django_user_model.objects.create_user("user"))


def test_create_and_save_next(client, entities, image_upload):
    p, c, u = entities
    data = {
        "name": "Mont",
        "person": p.pk,
        "category": c.pk,
        "storage_unit": u.pk,
        "primary_color": "Siyah",
        "status": "ACTIVE",
        "photos": image_upload(),
        "save_next": "1",
    }
    response = client.post(reverse("item-create"), data)
    assert response.status_code == 302 and response.url == reverse("item-create")
    obj = Item.objects.get()
    assert obj.photos.count() == 1
    response = client.get(reverse("item-create"))
    assert response.context["form"].initial["person"] == p.pk


def test_move_unit_and_location_follows(client, entities):
    p, c, u = entities
    new = StorageUnit.objects.create(name="Poşet 2", unit_type="VACUUM_BAG", location_text="Balkon")
    obj = Item.objects.create(
        name="Mont", person=p, category=c, storage_unit=u, primary_color="Siyah"
    )
    data = {
        "name": obj.name,
        "person": p.pk,
        "category": c.pk,
        "storage_unit": new.pk,
        "primary_color": "Siyah",
        "status": "ACTIVE",
    }
    assert client.post(reverse("item-update", args=[obj.pk]), data).status_code == 302
    obj.refresh_from_db()
    assert obj.physical_location == "Balkon"
    new.location_text = "Üst raf"
    new.save()
    obj.refresh_from_db()
    response = client.get(reverse("item-detail", args=[obj.pk]))
    assert b"\xc3\x9cst raf" in response.content


def test_create_item_with_multiple_photos(client, entities, image_upload):
    person, category, unit = entities
    response = client.post(
        reverse("item-create"),
        {
            "name": "Çok fotoğraflı mont",
            "person": person.pk,
            "category": category.pk,
            "storage_unit": unit.pk,
            "primary_color": "Siyah",
            "status": Item.Status.ACTIVE,
            "photos": [image_upload(name="front.jpg"), image_upload(name="back.jpg")],
        },
    )

    assert response.status_code == 302
    created_item = Item.objects.get(name="Çok fotoğraflı mont")
    photos = list(created_item.photos.all())
    assert len(photos) == 2
    assert photos[0].is_cover is True
    assert photos[0].thumbnail
    assert photos[1].is_cover is False


def test_catalog_filters_by_storage_unit(client, entities):
    person, category, wanted_unit = entities
    other_unit = StorageUnit.objects.create(
        name="Başka raf", unit_type=StorageUnit.Type.SHELF, location_text="Salon"
    )
    wanted = Item.objects.create(
        name="Aranan mont",
        person=person,
        category=category,
        storage_unit=wanted_unit,
        primary_color="Siyah",
    )
    Item.objects.create(
        name="Diğer mont",
        person=person,
        category=category,
        storage_unit=other_unit,
        primary_color="Mavi",
    )

    response = client.get(reverse("catalog"), {"storage_unit": wanted_unit.pk})

    assert response.status_code == 200
    assert list(response.context["page_obj"].object_list) == [wanted]
    assert response.context["result_count"] == 1


def test_archive_view_hides_item_from_catalog(client, entities):
    person, category, unit = entities
    item = Item.objects.create(
        name="Arşivlenecek mont",
        person=person,
        category=category,
        storage_unit=unit,
        primary_color="Siyah",
    )

    response = client.post(reverse("item-archive", args=[item.pk]))

    assert response.status_code == 302
    item.refresh_from_db()
    assert item.status == Item.Status.ARCHIVED
    assert item.archived_at is not None
    assert not Item.objects.visible().filter(pk=item.pk).exists()
