from django.contrib import admin

from .models import Category, Item, Person, Photo, StorageUnit, Tag


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "person", "category", "storage_unit", "status")
    list_filter = ("status", "person", "category", "storage_unit")
    search_fields = ("name", "brand", "model", "notes")
    inlines = [PhotoInline]


admin.site.register([Person, Category, StorageUnit, Tag])
