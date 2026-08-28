import tempfile
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .filters import filter_items
from .forms import (
    CategoryForm,
    ItemForm,
    PersonForm,
    PhotoForm,
    PortableRestoreConfirmForm,
    PortableRestoreUploadForm,
    StorageUnitForm,
    TagForm,
)
from .models import Category, Item, Person, Photo, StorageUnit, Tag
from .services.portable_backup import (
    PortableBackupError,
    build_portable_backup,
    cleanup_staged_backup,
    domain_has_data,
    restore_portable_backup,
    stage_uploaded_backup,
    validate_portable_backup,
)

PORTABLE_BACKUP_TOKEN_SALT = "inventory.portable-backup"
PORTABLE_BACKUP_TOKEN_MAX_AGE = 30 * 60


@login_required
def catalog(request):
    base = (
        Item.objects.visible()
        .filter(person__is_active=True, category__is_active=True, storage_unit__is_active=True)
        .select_related("person", "category", "storage_unit")
        .prefetch_related("photos", "tags")
    )
    items = filter_items(base, request.GET)
    page = Paginator(items, 24).get_page(request.GET.get("page"))
    text_filter_labels = [
        ("color", "Ana renk"),
        ("secondary_color", "İkincil renk"),
        ("brand", "Marka"),
        ("size", "Beden"),
        ("waist_size", "Bel ölçüsü"),
        ("inseam_size", "Paça uzunluğu"),
        ("shoe_size", "Ayakkabı numarası"),
        ("material", "Kumaş"),
        ("pattern", "Desen"),
        ("fit", "Fit"),
        ("season", "Mevsim"),
    ]
    context = {
        "page_obj": page,
        "result_count": items.count(),
        "people": Person.objects.filter(is_active=True),
        "categories": Category.objects.filter(is_active=True),
        "units": StorageUnit.objects.filter(is_active=True),
        "tags": Tag.objects.all(),
        "statuses": Item.Status.choices,
        "unit_types": StorageUnit.Type.choices,
        "text_filters": [
            (key, label, request.GET.get(key, "")) for key, label in text_filter_labels
        ],
        "active_filters": [(k, v) for k, v in request.GET.items() if v and k != "page"],
    }
    template = (
        "inventory/_item_grid.html"
        if request.headers.get("HX-Request")
        else "inventory/catalog.html"
    )
    return render(request, template, context)


@login_required
def item_detail(request, pk):
    item = get_object_or_404(
        Item.objects.select_related("person", "category", "storage_unit").prefetch_related(
            "photos", "tags"
        ),
        pk=pk,
    )
    return render(request, "inventory/item_detail.html", {"item": item})


@login_required
def item_create(request):
    initial = {k: request.session.get(f"last_{k}") for k in ("person", "storage_unit", "category")}
    form = ItemForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            item = form.save()
            form.save_photos(item)
        if "save_next" in request.POST:
            for key in ("person", "storage_unit", "category"):
                request.session[f"last_{key}"] = getattr(item, f"{key}_id")
            messages.success(request, "Ürün kaydedildi. Sonraki ürünü ekleyebilirsiniz.")
            return redirect("item-create")
        messages.success(request, "Ürün kaydedildi.")
        return redirect("item-detail", pk=item.pk)
    return render(request, "inventory/item_form.html", {"form": form, "title": "Ürün ekle"})


@login_required
def item_update(request, pk):
    item = get_object_or_404(Item, pk=pk)
    form = ItemForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            item = form.save()
            form.save_photos(item)
        messages.success(request, "Ürün güncellendi.")
        return redirect("item-detail", pk=item.pk)
    return render(
        request, "inventory/item_form.html", {"form": form, "title": "Ürünü düzenle", "item": item}
    )


@login_required
def item_archive(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if request.method == "POST":
        item.archive()
        messages.success(request, "Ürün arşivlendi.")
        return redirect("catalog")
    return render(request, "inventory/confirm.html", {"object": item, "action": "arşivlemek"})


@login_required
def photo_add(request, pk):
    item = get_object_or_404(Item, pk=pk)
    form = PhotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        photo = form.save(commit=False)
        photo.item = item
        photo.save()
        return redirect("item-detail", pk=pk)
    return render(request, "inventory/generic_form.html", {"form": form, "title": "Fotoğraf ekle"})


@login_required
def photo_cover(request, pk):
    photo = get_object_or_404(Photo, pk=pk)
    if request.method == "POST":
        photo.set_as_cover()
    return redirect("item-detail", pk=photo.item_id)


@login_required
def photo_delete(request, pk):
    photo = get_object_or_404(Photo, pk=pk)
    item_id = photo.item_id
    if request.method == "POST":
        photo.delete()
    return redirect("item-detail", pk=item_id)


@login_required
def storage_detail(request, pk):
    unit = get_object_or_404(StorageUnit, pk=pk)
    items = (
        unit.items.visible()
        .select_related("person", "category", "storage_unit")
        .prefetch_related("photos")
    )
    return render(request, "inventory/storage_detail.html", {"unit": unit, "items": items})


@login_required
def manage(request):
    return render(
        request,
        "inventory/manage.html",
        {
            "people": Person.objects.all(),
            "categories": Category.objects.all(),
            "units": StorageUnit.objects.all(),
            "tags": Tag.objects.all(),
        },
    )


CRUD = {
    "people": (Person, PersonForm),
    "categories": (Category, CategoryForm),
    "units": (StorageUnit, StorageUnitForm),
    "tags": (Tag, TagForm),
}


def crud_config(kind):
    return CRUD[kind]


@login_required
def crud_create(request, kind):
    model, form_cls = crud_config(kind)
    form = form_cls(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("manage")
    return render(
        request,
        "inventory/generic_form.html",
        {"form": form, "title": f"Yeni {model._meta.verbose_name}"},
    )


@login_required
def crud_update(request, kind, pk):
    model, form_cls = crud_config(kind)
    obj = get_object_or_404(model, pk=pk)
    form = form_cls(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("manage")
    return render(
        request,
        "inventory/generic_form.html",
        {"form": form, "title": f"{model._meta.verbose_name} düzenle"},
    )


@login_required
def crud_delete(request, kind, pk):
    model, _ = crud_config(kind)
    obj = get_object_or_404(model, pk=pk)
    if request.method == "POST":
        try:
            obj.delete()
            messages.success(request, "Kayıt silindi.")
        except Exception:
            messages.error(request, "Bu kayıt kullanımda olduğu için silinemedi.")
        return redirect("manage")
    return render(
        request, "inventory/confirm.html", {"object": obj, "action": "kalıcı olarak silmek"}
    )


@login_required
def item_delete(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Ürün kalıcı olarak silindi.")
        return redirect("catalog")
    return render(
        request, "inventory/confirm.html", {"object": item, "action": "kalıcı olarak silmek"}
    )


@staff_member_required
@require_http_methods(["GET", "POST"])
def backup_settings(request):
    summary = {
        "items": Item.objects.count(),
        "photos": Photo.objects.count(),
        "people": Person.objects.count(),
        "categories": Category.objects.count(),
        "storage_units": StorageUnit.objects.count(),
        "tags": Tag.objects.count(),
    }
    upload_form = PortableRestoreUploadForm()
    confirm_form = None
    preview = None
    restore_result = None

    if request.method == "POST" and request.POST.get("action") == "export":
        filename, backup = build_portable_backup()
        response = FileResponse(backup, as_attachment=True, filename=filename)
        response["Content-Type"] = "application/zip"
        return response

    if request.method == "POST" and request.POST.get("action") == "preview":
        upload_form = PortableRestoreUploadForm(request.POST, request.FILES)
        if upload_form.is_valid():
            try:
                path, validated = stage_uploaded_backup(upload_form.cleaned_data["backup_file"])
                signed_value = signing.dumps(
                    {"path": str(path), "user_id": request.user.pk},
                    salt=PORTABLE_BACKUP_TOKEN_SALT,
                )
                preview = validated.manifest
                confirm_form = PortableRestoreConfirmForm(initial={"token": signed_value})
            except PortableBackupError as exc:
                upload_form.add_error("backup_file", str(exc))

    if request.method == "POST" and request.POST.get("action") == "restore":
        confirm_form = PortableRestoreConfirmForm(request.POST)
        if confirm_form.is_valid():
            path = None
            try:
                payload = signing.loads(
                    confirm_form.cleaned_data["token"],
                    salt=PORTABLE_BACKUP_TOKEN_SALT,
                    max_age=PORTABLE_BACKUP_TOKEN_MAX_AGE,
                )
                if payload.get("user_id") != request.user.pk:
                    raise PortableBackupError("Restore onayı bu kullanıcıya ait değil.")
                path = Path(payload["path"])
                stage_root = Path(tempfile.gettempdir()) / "closet-vault-portable-backups"
                if path.parent != stage_root or not path.is_file():
                    raise PortableBackupError(
                        "Geçici restore dosyası bulunamadı veya süresi doldu."
                    )
                with path.open("rb") as source:
                    validated = validate_portable_backup(source)
                restore_result = restore_portable_backup(validated)
                messages.success(request, "Portable yedek başarıyla geri yüklendi.")
            except signing.BadSignature:
                messages.error(request, "Restore onayı geçersiz veya süresi dolmuş.")
            except PortableBackupError as exc:
                messages.error(request, str(exc))
            except Exception:
                messages.error(
                    request,
                    "Restore beklenmeyen bir hata nedeniyle tamamlanamadı; "
                    "hiçbir veri uygulanmadı.",
                )
            finally:
                if path:
                    cleanup_staged_backup(path)

    return render(
        request,
        "inventory/backup_settings.html",
        {
            "summary": summary,
            "upload_form": upload_form,
            "confirm_form": confirm_form,
            "preview": preview,
            "restore_result": restore_result,
            "has_domain_data": domain_has_data(),
        },
    )
