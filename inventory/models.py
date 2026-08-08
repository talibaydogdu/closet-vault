from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from .services.image_processing import make_thumbnail, process_image


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Person(TimestampedModel):
    name = models.CharField("Ad", max_length=100, unique=True)
    is_active = models.BooleanField("Aktif", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Kişi"
        verbose_name_plural = "Kişiler"

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField("Ad", max_length=100)
    parent = models.ForeignKey(
        "self",
        verbose_name="Üst kategori",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    is_active = models.BooleanField("Aktif", default=True)
    sort_order = models.PositiveIntegerField("Sıra", default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["parent", "name"], name="unique_category_parent_name")
        ]

    def __str__(self):
        return f"{self.parent} › {self.name}" if self.parent else self.name


class StorageUnit(TimestampedModel):
    class Type(models.TextChoices):
        VACUUM_BAG = "VACUUM_BAG", "Vakum poşeti"
        SUITCASE = "SUITCASE", "Valiz"
        SHELF = "SHELF", "Raf"
        DRAWER = "DRAWER", "Çekmece"
        HANGING = "HANGING", "Askılık bölümü"
        OTHER = "OTHER", "Diğer"

    name = models.CharField("Ad", max_length=150, unique=True)
    unit_type = models.CharField("Tür", max_length=20, choices=Type.choices)
    location_text = models.CharField("Fiziksel konum", max_length=255)
    description = models.TextField("Açıklama", blank=True)
    is_active = models.BooleanField("Aktif", default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(
                fields=["unit_type", "is_active"],
                name="inventory_s_unit_ty_5da087_idx",
            )
        ]

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField("Ad", max_length=80, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name, allow_unicode=True) or "etiket"
            candidate, number = base, 2
            while Tag.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate, number = f"{base}-{number}", number + 1
            self.slug = candidate
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ItemQuerySet(models.QuerySet):
    def visible(self):
        return self.exclude(status=Item.Status.ARCHIVED).filter(archived_at__isnull=True)


class Item(TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Envanterde"
        TO_SELL = "TO_SELL", "Satılacak"
        TO_DONATE = "TO_DONATE", "Bağışlanacak"
        SOLD = "SOLD", "Satıldı"
        DONATED = "DONATED", "Bağışlandı"
        ARCHIVED = "ARCHIVED", "Arşivlendi"
        LOST = "LOST", "Kayıp"

    name = models.CharField("Ürün adı", max_length=180)
    person = models.ForeignKey(
        Person, verbose_name="Kişi", on_delete=models.PROTECT, related_name="items"
    )
    category = models.ForeignKey(
        Category, verbose_name="Kategori", on_delete=models.PROTECT, related_name="items"
    )
    storage_unit = models.ForeignKey(
        StorageUnit, verbose_name="Saklama birimi", on_delete=models.PROTECT, related_name="items"
    )
    brand = models.CharField("Marka", max_length=100, blank=True)
    model = models.CharField("Model", max_length=100, blank=True)
    primary_color = models.CharField("Ana renk", max_length=60)
    secondary_color = models.CharField("İkincil renk", max_length=60, blank=True)
    size = models.CharField("Beden", max_length=30, blank=True)
    waist_size = models.CharField("Bel ölçüsü", max_length=30, blank=True)
    inseam_size = models.CharField("Paça uzunluğu", max_length=30, blank=True)
    shoe_size = models.CharField("Ayakkabı numarası", max_length=20, blank=True)
    material = models.CharField("Kumaş", max_length=80, blank=True)
    pattern = models.CharField("Desen", max_length=80, blank=True)
    fit = models.CharField("Fit", max_length=80, blank=True)
    season = models.CharField("Mevsim", max_length=80, blank=True)
    status = models.CharField("Durum", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    notes = models.TextField("Notlar", blank=True)
    tags = models.ManyToManyField(Tag, verbose_name="Etiketler", blank=True, related_name="items")
    archived_at = models.DateTimeField(blank=True, null=True)
    objects = ItemQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "archived_at"], name="inventory_i_status_919cd0_idx"),
            models.Index(fields=["person", "category"], name="inventory_i_person__ab3c85_idx"),
            models.Index(fields=["primary_color"], name="inventory_i_primary_17917f_idx"),
            models.Index(fields=["brand"], name="inventory_i_brand_18c50c_idx"),
            models.Index(fields=["storage_unit"], name="inventory_i_storage_1740e7_idx"),
        ]

    @property
    def physical_location(self):
        return self.storage_unit.location_text

    @property
    def cover_photo(self):
        return next((p for p in self.photos.all() if p.is_cover), None)

    def archive(self):
        self.status, self.archived_at = self.Status.ARCHIVED, timezone.now()
        self.save(update_fields=["status", "archived_at", "updated_at"])

    def __str__(self):
        return self.name


def photo_path(instance, filename):
    return f"items/{instance.item_id}/{filename}"


def thumbnail_path(instance, filename):
    return f"items/{instance.item_id}/thumbs/{filename}"


class Photo(models.Model):
    item = models.ForeignKey(
        Item, verbose_name="Ürün", on_delete=models.CASCADE, related_name="photos"
    )
    image = models.ImageField("Fotoğraf", upload_to=photo_path)
    thumbnail = models.ImageField("Thumbnail", upload_to=thumbnail_path, blank=True)
    is_cover = models.BooleanField("Ana fotoğraf", default=False)
    sort_order = models.PositiveIntegerField("Sıra", default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item"], condition=Q(is_cover=True), name="one_cover_per_item"
            )
        ]

    def clean(self):
        if (
            self.is_cover
            and Photo.objects.exclude(pk=self.pk).filter(item=self.item, is_cover=True).exists()
        ):
            raise ValidationError({"is_cover": "Bir üründe yalnızca bir ana fotoğraf olabilir."})

    def save(self, *args, **kwargs):
        new = self._state.adding
        if new:
            self.is_cover = self.is_cover or not Photo.objects.filter(item=self.item).exists()
            self.image = process_image(self.image)
        with transaction.atomic():
            if self.is_cover:
                Photo.objects.filter(item=self.item, is_cover=True).exclude(pk=self.pk).update(
                    is_cover=False
                )
            super().save(*args, **kwargs)
            if self.is_cover and not self.thumbnail:
                self.thumbnail = make_thumbnail(self.image)
                super().save(update_fields=["thumbnail"])

    def set_as_cover(self):
        self.is_cover = True
        self.save()

    def delete(self, *args, **kwargs):
        image_name, thumb_name, item = self.image.name, self.thumbnail.name, self.item
        was_cover = self.is_cover
        result = super().delete(*args, **kwargs)
        self.image.storage.delete(image_name)
        if thumb_name:
            self.thumbnail.storage.delete(thumb_name)
        if was_cover:
            replacement = item.photos.first()
            if replacement:
                replacement.set_as_cover()
        return result

    def __str__(self):
        return f"{self.item} fotoğrafı"
