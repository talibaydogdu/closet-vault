from django import forms
from django.core.exceptions import ValidationError

from .models import Category, Item, Person, Photo, StorageUnit, Tag


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        clean_one = super().clean
        return (
            [clean_one(file, initial) for file in data]
            if isinstance(data, (list, tuple))
            else ([clean_one(data, initial)] if data else [])
        )


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "form-select"
                    if isinstance(field.widget, (forms.Select, forms.SelectMultiple))
                    else "form-control"
                ),
            )
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"


class ItemForm(StyledModelForm):
    photos = MultipleFileField(
        label="Fotoğraflar",
        required=False,
        widget=MultipleFileInput(
            attrs={"accept": "image/*", "capture": "environment", "class": "form-control"}
        ),
    )

    class Meta:
        model = Item
        fields = [
            "name",
            "person",
            "category",
            "primary_color",
            "storage_unit",
            "brand",
            "size",
            "model",
            "secondary_color",
            "waist_size",
            "inseam_size",
            "shoe_size",
            "material",
            "pattern",
            "fit",
            "season",
            "status",
            "tags",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_photos(self):
        photos = self.cleaned_data.get("photos", [])
        if not self.instance.pk and not photos:
            raise ValidationError("En az bir fotoğraf yüklemelisiniz.")
        return photos

    def save_photos(self, item):
        for position, upload in enumerate(
            self.cleaned_data.get("photos", []), start=item.photos.count()
        ):
            Photo.objects.create(item=item, image=upload, sort_order=position)


class PhotoForm(StyledModelForm):
    class Meta:
        model = Photo
        fields = ["image", "sort_order"]


class PersonForm(StyledModelForm):
    class Meta:
        model = Person
        fields = ["name", "is_active"]


class CategoryForm(StyledModelForm):
    class Meta:
        model = Category
        fields = ["name", "parent", "is_active", "sort_order"]


class StorageUnitForm(StyledModelForm):
    class Meta:
        model = StorageUnit
        fields = ["name", "unit_type", "location_text", "description", "is_active"]


class TagForm(StyledModelForm):
    class Meta:
        model = Tag
        fields = ["name"]


class PortableRestoreUploadForm(forms.Form):
    backup_file = forms.FileField(
        label="Portable backup ZIP dosyası",
        widget=forms.ClearableFileInput(attrs={"accept": ".zip,application/zip"}),
    )

    def clean_backup_file(self):
        from .services.portable_backup import MAX_ARCHIVE_SIZE

        upload = self.cleaned_data["backup_file"]
        if upload.size > MAX_ARCHIVE_SIZE:
            raise ValidationError("Yedek dosyası izin verilen boyutu aşıyor.")
        return upload


class PortableRestoreConfirmForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(
        label="Bu kurulumun envanterinin boş olduğunu ve restore işlemini onaylıyorum."
    )
