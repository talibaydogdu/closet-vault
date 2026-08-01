from django.urls import path
from . import views
urlpatterns = [
 path("", views.catalog, name="catalog"), path("urun/yeni/", views.item_create, name="item-create"),
 path("urun/<int:pk>/", views.item_detail, name="item-detail"), path("urun/<int:pk>/duzenle/", views.item_update, name="item-update"),
 path("urun/<int:pk>/arsivle/", views.item_archive, name="item-archive"), path("urun/<int:pk>/sil/", views.item_delete, name="item-delete"),
 path("urun/<int:pk>/fotograf/", views.photo_add, name="photo-add"), path("fotograf/<int:pk>/kapak/", views.photo_cover, name="photo-cover"), path("fotograf/<int:pk>/sil/", views.photo_delete, name="photo-delete"),
 path("saklama/<int:pk>/", views.storage_detail, name="storage-detail"), path("yonetim/", views.manage, name="manage"),
 path("yonetim/<str:kind>/yeni/", views.crud_create, name="crud-create"), path("yonetim/<str:kind>/<int:pk>/duzenle/", views.crud_update, name="crud-update"), path("yonetim/<str:kind>/<int:pk>/sil/", views.crud_delete, name="crud-delete"),
]
