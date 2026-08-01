import pytest
from django.urls import reverse
from inventory.models import Item, Photo, StorageUnit
pytestmark=pytest.mark.django_db
@pytest.fixture(autouse=True)
def login(client,django_user_model): client.force_login(django_user_model.objects.create_user("user"))
def test_create_and_save_next(client,entities,image_upload):
    p,c,u=entities; data={"name":"Mont","person":p.pk,"category":c.pk,"storage_unit":u.pk,"primary_color":"Siyah","status":"ACTIVE","photos":image_upload(),"save_next":"1"}
    response=client.post(reverse("item-create"),data); assert response.status_code==302 and response.url==reverse("item-create")
    obj=Item.objects.get(); assert obj.photos.count()==1
    response=client.get(reverse("item-create")); assert response.context["form"].initial["person"]==p.pk

def test_move_unit_and_location_follows(client,entities):
    p,c,u=entities; new=StorageUnit.objects.create(name="Poşet 2",unit_type="VACUUM_BAG",location_text="Balkon")
    obj=Item.objects.create(name="Mont",person=p,category=c,storage_unit=u,primary_color="Siyah")
    data={"name":obj.name,"person":p.pk,"category":c.pk,"storage_unit":new.pk,"primary_color":"Siyah","status":"ACTIVE"}
    assert client.post(reverse("item-update",args=[obj.pk]),data).status_code==302
    obj.refresh_from_db(); assert obj.physical_location=="Balkon"
    new.location_text="Üst raf"; new.save(); obj.refresh_from_db()
    response=client.get(reverse("item-detail",args=[obj.pk])); assert b"\xc3\x9cst raf" in response.content
