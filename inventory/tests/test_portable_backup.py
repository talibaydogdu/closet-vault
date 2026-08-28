import json
import zipfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from inventory.models import Category, Item, Person, Photo, StorageUnit, Tag
from inventory.services.portable_backup import (
    PortableBackupError,
    build_portable_backup,
    restore_portable_backup,
    validate_portable_backup,
)

pytestmark = pytest.mark.django_db


def populated_inventory(entities, image_upload):
    person, root, unit = entities
    child = Category.objects.create(name="Kaban", parent=root, sort_order=2)
    tag = Tag.objects.create(name="Kışlık")
    item = Item.objects.create(
        name="Kışlık kaban",
        person=person,
        category=child,
        storage_unit=unit,
        primary_color="Siyah",
        status=Item.Status.ACTIVE,
    )
    item.tags.add(tag)
    photo = Photo.objects.create(item=item, image=image_upload((2400, 1200)))
    return {
        "person": person,
        "root": root,
        "child": child,
        "unit": unit,
        "tag": tag,
        "item": item,
        "photo": photo,
    }


def backup_bytes():
    _, stream = build_portable_backup()
    try:
        return stream.read()
    finally:
        stream.close()


def rewrite_zip(content, transform):
    source = zipfile.ZipFile(BytesIO(content))
    files = {info.filename: source.read(info.filename) for info in source.infolist()}
    source.close()
    transform(files)
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            archive.writestr(name, value)
    output.seek(0)
    return output


def clear_domain_data():
    Photo.objects.all().delete()
    Item.objects.all().delete()
    while Category.objects.exists():
        Category.objects.filter(children__isnull=True).delete()
    Person.objects.all().delete()
    StorageUnit.objects.all().delete()
    Tag.objects.all().delete()


def test_export_zip_contains_manifest_data_and_media(entities, image_upload):
    populated_inventory(entities, image_upload)
    filename, stream = build_portable_backup()

    assert filename.startswith("closet-vault-backup-") and filename.endswith(".zip")
    with zipfile.ZipFile(stream) as archive:
        names = set(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        data = json.loads(archive.read("data.json"))
    assert {"manifest.json", "data.json"}.issubset(names)
    assert data["photos"][0]["media_path"] in names
    assert manifest["backup_format_version"] == 1
    assert manifest["counts"]["items"] == 1


def test_export_clean_database_import_preserves_relations(entities, image_upload):
    original = populated_inventory(entities, image_upload)
    expected = {
        "people": Person.objects.count(),
        "categories": Category.objects.count(),
        "units": StorageUnit.objects.count(),
        "tags": Tag.objects.count(),
        "items": Item.objects.count(),
        "photos": Photo.objects.count(),
    }
    validated = validate_portable_backup(BytesIO(backup_bytes()))
    clear_domain_data()

    result = restore_portable_backup(validated)

    assert result["items"] == expected["items"]
    assert Person.objects.count() == expected["people"]
    assert Category.objects.count() == expected["categories"]
    assert StorageUnit.objects.count() == expected["units"]
    assert Tag.objects.count() == expected["tags"]
    assert Item.objects.count() == expected["items"]
    assert Photo.objects.count() == expected["photos"]
    restored = (
        Item.objects.select_related("category", "storage_unit")
        .prefetch_related("tags", "photos")
        .get()
    )
    assert restored.category.parent.name == original["root"].name
    assert restored.storage_unit.name == original["unit"].name
    assert list(restored.tags.values_list("name", flat=True)) == [original["tag"].name]
    assert restored.photos.get().is_cover is True
    assert restored.photos.get().thumbnail


def test_invalid_zip_is_rejected_without_changes():
    with pytest.raises(PortableBackupError, match="ZIP"):
        validate_portable_backup(BytesIO(b"not a zip"))
    assert not Item.objects.exists()


def test_unsupported_backup_version_is_rejected(entities, image_upload):
    populated_inventory(entities, image_upload)

    def change_version(files):
        manifest = json.loads(files["manifest.json"])
        manifest["backup_format_version"] = 999
        files["manifest.json"] = json.dumps(manifest).encode()

    with pytest.raises(PortableBackupError, match="desteklenmiyor"):
        validate_portable_backup(rewrite_zip(backup_bytes(), change_version))


def test_missing_media_is_rejected(entities, image_upload):
    populated_inventory(entities, image_upload)

    def remove_media(files):
        media_name = next(name for name in files if name.startswith("media/photos/"))
        del files[media_name]

    with pytest.raises(PortableBackupError, match="Media dosyası eksik"):
        validate_portable_backup(rewrite_zip(backup_bytes(), remove_media))


def test_path_traversal_is_rejected(entities, image_upload):
    populated_inventory(entities, image_upload)

    def add_traversal(files):
        files["../secret.txt"] = b"unsafe"

    with pytest.raises(PortableBackupError, match="güvenli olmayan"):
        validate_portable_backup(rewrite_zip(backup_bytes(), add_traversal))


def test_import_error_rolls_back_all_domain_data(entities, image_upload):
    populated_inventory(entities, image_upload)
    content = backup_bytes()

    def corrupt_media_with_matching_hash(files):
        data = json.loads(files["data.json"])
        media_path = data["photos"][0]["media_path"]
        files[media_path] = b"not an image"
        import hashlib

        data["photos"][0]["sha256"] = hashlib.sha256(files[media_path]).hexdigest()
        files["data.json"] = json.dumps(data).encode()

    validated = validate_portable_backup(rewrite_zip(content, corrupt_media_with_matching_hash))
    clear_domain_data()
    with pytest.raises(Exception):
        restore_portable_backup(validated)
    assert not any(
        model.objects.exists() for model in (Photo, Item, Category, Person, StorageUnit, Tag)
    )


def test_backup_page_requires_staff(client, django_user_model):
    user = django_user_model.objects.create_user("normal")
    client.force_login(user)
    response = client.get(reverse("backup-settings"))
    assert response.status_code == 302

    user.is_staff = True
    user.save()
    response = client.get(reverse("backup-settings"))
    assert response.status_code == 200


def test_export_view_downloads_zip_for_staff(client, django_user_model, entities, image_upload):
    populated_inventory(entities, image_upload)
    staff = django_user_model.objects.create_user("staff", is_staff=True)
    client.force_login(staff)

    response = client.post(reverse("backup-settings"), {"action": "export"})

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    content = b"".join(response.streaming_content)
    with zipfile.ZipFile(BytesIO(content)) as archive:
        assert "manifest.json" in archive.namelist()


def test_preview_and_confirm_restore_flow(client, django_user_model, entities, image_upload):
    populated_inventory(entities, image_upload)
    content = backup_bytes()
    clear_domain_data()
    staff = django_user_model.objects.create_user("restore-staff", is_staff=True)
    client.force_login(staff)

    preview_response = client.post(
        reverse("backup-settings"),
        {
            "action": "preview",
            "backup_file": SimpleUploadedFile(
                "closet-vault-backup.zip", content, content_type="application/zip"
            ),
        },
    )

    assert preview_response.status_code == 200
    assert preview_response.context["preview"]["counts"]["items"] == 1
    token = preview_response.context["confirm_form"].initial["token"]
    restore_response = client.post(
        reverse("backup-settings"), {"action": "restore", "token": token, "confirm": "on"}
    )
    assert restore_response.status_code == 200
    assert restore_response.context["restore_result"]["items"] == 1
    assert Item.objects.get().photos.count() == 1
