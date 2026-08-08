import pytest

from inventory.filters import filter_items
from inventory.models import Category, Item, Person, StorageUnit, Tag

pytestmark = pytest.mark.django_db


def test_all_filters_and_archived(entities):
    p, c, u = entities
    tag = Tag.objects.create(name="Kış")
    wanted = Item.objects.create(
        name="Siyah Mont", person=p, category=c, storage_unit=u, primary_color="Siyah", brand="X"
    )
    wanted.tags.add(tag)
    other_p = Person.objects.create(name="Eşim")
    other_c = Category.objects.create(name="Gömlek")
    other_u = StorageUnit.objects.create(name="Raf", unit_type="SHELF", location_text="Oda")
    archived = Item.objects.create(
        name="Eski", person=other_p, category=other_c, storage_unit=other_u, primary_color="Mavi"
    )
    archived.archive()
    for params in (
        {"person": p.pk},
        {"category": c.pk},
        {"color": "Siyah"},
        {"storage_unit": u.pk},
        {"tag": tag.pk},
        {"person": p.pk, "category": c.pk, "color": "Siyah", "storage_unit": u.pk},
    ):
        assert list(filter_items(Item.objects.visible(), params)) == [wanted]
    assert archived not in Item.objects.visible()
