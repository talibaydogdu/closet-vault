import hashlib
import json
import os
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import NAMESPACE_URL, uuid5

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from inventory.models import Category, Item, Person, Photo, StorageUnit, Tag

BACKUP_FORMAT_VERSION = 1
APP_NAME = "Closet Vault"
APP_VERSION = "1.0.0"
MAX_ARCHIVE_SIZE = 1024 * 1024 * 1024
MAX_UNCOMPRESSED_SIZE = 2 * 1024 * 1024 * 1024
MAX_FILES = 50_000
MAX_COMPRESSION_RATIO = 200
REQUIRED_DATA_KEYS = {"people", "categories", "storage_units", "tags", "items", "photos"}
DOMAIN_MODELS = (Photo, Item, Category, Person, StorageUnit, Tag)


class PortableBackupError(Exception):
    """A safe, user-facing portable backup validation or restore error."""


@dataclass(frozen=True)
class ValidatedBackup:
    manifest: dict
    data: dict
    media: dict[str, bytes]


def _reference(kind, pk):
    return str(uuid5(NAMESPACE_URL, f"closet-vault:{kind}:{pk}"))


def _iso(value):
    return value.isoformat() if value else None


def _sha256(content):
    return hashlib.sha256(content).hexdigest()


def _read_field(field):
    field.open("rb")
    try:
        return field.read()
    finally:
        field.close()


def build_portable_backup():
    people = list(Person.objects.all())
    categories = list(Category.objects.select_related("parent").all())
    units = list(StorageUnit.objects.all())
    tags = list(Tag.objects.all())
    items = list(
        Item.objects.select_related("person", "category", "storage_unit").prefetch_related("tags")
    )
    photos = list(Photo.objects.select_related("item").order_by("item_id", "sort_order", "pk"))

    refs = {
        "person": {obj.pk: _reference("person", obj.pk) for obj in people},
        "category": {obj.pk: _reference("category", obj.pk) for obj in categories},
        "unit": {obj.pk: _reference("storage-unit", obj.pk) for obj in units},
        "tag": {obj.pk: _reference("tag", obj.pk) for obj in tags},
        "item": {obj.pk: _reference("item", obj.pk) for obj in items},
        "photo": {obj.pk: _reference("photo", obj.pk) for obj in photos},
    }
    photo_data = []
    for photo in photos:
        content = _read_field(photo.image)
        suffix = Path(photo.image.name).suffix.lower() or ".webp"
        media_path = f"media/photos/{refs['photo'][photo.pk]}{suffix}"
        photo_data.append(
            {
                "ref": refs["photo"][photo.pk],
                "item_ref": refs["item"][photo.item_id],
                "media_path": media_path,
                "sha256": _sha256(content),
                "is_cover": photo.is_cover,
                "sort_order": photo.sort_order,
                "created_at": _iso(photo.created_at),
            }
        )

    data = {
        "people": [
            {
                "ref": refs["person"][obj.pk],
                "name": obj.name,
                "is_active": obj.is_active,
                "created_at": _iso(obj.created_at),
                "updated_at": _iso(obj.updated_at),
            }
            for obj in people
        ],
        "categories": [
            {
                "ref": refs["category"][obj.pk],
                "name": obj.name,
                "parent_ref": refs["category"].get(obj.parent_id),
                "is_active": obj.is_active,
                "sort_order": obj.sort_order,
            }
            for obj in categories
        ],
        "storage_units": [
            {
                "ref": refs["unit"][obj.pk],
                "name": obj.name,
                "unit_type": obj.unit_type,
                "location_text": obj.location_text,
                "description": obj.description,
                "is_active": obj.is_active,
                "created_at": _iso(obj.created_at),
                "updated_at": _iso(obj.updated_at),
            }
            for obj in units
        ],
        "tags": [
            {
                "ref": refs["tag"][obj.pk],
                "name": obj.name,
                "slug": obj.slug,
                "created_at": _iso(obj.created_at),
            }
            for obj in tags
        ],
        "items": [
            {
                "ref": refs["item"][obj.pk],
                "name": obj.name,
                "person_ref": refs["person"][obj.person_id],
                "category_ref": refs["category"][obj.category_id],
                "storage_unit_ref": refs["unit"][obj.storage_unit_id],
                "tag_refs": [refs["tag"][tag.pk] for tag in obj.tags.all()],
                "brand": obj.brand,
                "model": obj.model,
                "primary_color": obj.primary_color,
                "secondary_color": obj.secondary_color,
                "size": obj.size,
                "waist_size": obj.waist_size,
                "inseam_size": obj.inseam_size,
                "shoe_size": obj.shoe_size,
                "material": obj.material,
                "pattern": obj.pattern,
                "fit": obj.fit,
                "season": obj.season,
                "status": obj.status,
                "notes": obj.notes,
                "created_at": _iso(obj.created_at),
                "updated_at": _iso(obj.updated_at),
                "archived_at": _iso(obj.archived_at),
            }
            for obj in items
        ],
        "photos": photo_data,
    }
    now = timezone.now()
    manifest = {
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "application": APP_NAME,
        "application_version": APP_VERSION,
        "created_at": now.isoformat(),
        "counts": {
            "items": len(items),
            "photos": len(photos),
            "people": len(people),
            "categories": len(categories),
            "storage_units": len(units),
            "tags": len(tags),
        },
    }
    output = tempfile.SpooledTemporaryFile(max_size=20 * 1024 * 1024, mode="w+b")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=2))
        archive.writestr("media/", b"")
        for photo, row in zip(photos, photo_data, strict=True):
            archive.writestr(row["media_path"], _read_field(photo.image))
    output.seek(0)
    filename = f"closet-vault-backup-{now.strftime('%Y-%m-%d-%H%M')}.zip"
    return filename, output


def _safe_member_name(name):
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _load_json(archive, name):
    try:
        return json.loads(archive.read(name))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PortableBackupError(f"{name} eksik veya geçersiz JSON içeriyor.") from exc


def validate_portable_backup(source):
    try:
        source.seek(0, os.SEEK_END)
        size = source.tell()
        source.seek(0)
    except (AttributeError, OSError) as exc:
        raise PortableBackupError("Yedek dosyası okunamadı.") from exc
    if size > MAX_ARCHIVE_SIZE:
        raise PortableBackupError("Yedek dosyası izin verilen boyutu aşıyor.")
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_FILES:
                raise PortableBackupError("Yedek çok fazla dosya içeriyor.")
            filenames = [info.filename for info in infos]
            if len(filenames) != len(set(filenames)):
                raise PortableBackupError("Yedekte yinelenen dosya yolu bulundu.")
            total_size = 0
            for info in infos:
                if not _safe_member_name(info.filename):
                    raise PortableBackupError("Yedekte güvenli olmayan dosya yolu bulundu.")
                total_size += info.file_size
                if total_size > MAX_UNCOMPRESSED_SIZE:
                    raise PortableBackupError("Yedeğin açılmış boyutu izin verilen sınırı aşıyor.")
                if info.file_size and info.compress_size == 0:
                    raise PortableBackupError("Şüpheli sıkıştırılmış dosya bulundu.")
                if (
                    info.compress_size
                    and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
                ):
                    raise PortableBackupError(
                        "Şüpheli sıkıştırma oranı nedeniyle yedek reddedildi."
                    )
            manifest = _load_json(archive, "manifest.json")
            data = _load_json(archive, "data.json")
            if manifest.get("backup_format_version") != BACKUP_FORMAT_VERSION:
                raise PortableBackupError("Bu backup_format_version sürümü desteklenmiyor.")
            if manifest.get("application") != APP_NAME:
                raise PortableBackupError("Bu dosya Closet Vault portable yedeği değil.")
            if not isinstance(data, dict) or not REQUIRED_DATA_KEYS.issubset(data):
                raise PortableBackupError("data.json gerekli veri bölümlerini içermiyor.")
            if any(not isinstance(data[key], list) for key in REQUIRED_DATA_KEYS):
                raise PortableBackupError("data.json veri bölümleri liste olmalıdır.")
            counts = manifest.get("counts")
            count_keys = {
                "people": "people",
                "categories": "categories",
                "storage_units": "storage_units",
                "tags": "tags",
                "items": "items",
                "photos": "photos",
            }
            if not isinstance(counts, dict) or any(
                counts.get(manifest_key) != len(data[data_key])
                for manifest_key, data_key in count_keys.items()
            ):
                raise PortableBackupError("Manifest kayıt sayıları data.json ile uyuşmuyor.")
            names = {info.filename for info in infos}
            media = {}
            for photo in data["photos"]:
                if not isinstance(photo, dict) or not {
                    "ref",
                    "item_ref",
                    "media_path",
                    "sha256",
                }.issubset(photo):
                    raise PortableBackupError("Fotoğraf metadata kaydı eksik.")
                media_path = photo["media_path"]
                if not isinstance(media_path, str) or not media_path.startswith("media/"):
                    raise PortableBackupError("Fotoğraf media yolu geçersiz.")
                if media_path not in names:
                    raise PortableBackupError(f"Media dosyası eksik: {media_path}")
                content = archive.read(media_path)
                if _sha256(content) != photo["sha256"]:
                    raise PortableBackupError(f"Media dosyası doğrulanamadı: {media_path}")
                media[media_path] = content
    except (zipfile.BadZipFile, OSError) as exc:
        raise PortableBackupError("Geçerli bir ZIP yedek dosyası seçin.") from exc
    _validate_references(data)
    return ValidatedBackup(manifest=manifest, data=data, media=media)


def _index(records, label):
    result = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("ref"), str):
            raise PortableBackupError(f"{label} kaydında geçerli ref eksik.")
        if record["ref"] in result:
            raise PortableBackupError(f"{label} bölümünde yinelenen ref bulundu.")
        result[record["ref"]] = record
    return result


def _validate_references(data):
    people = _index(data["people"], "Kişi")
    categories = _index(data["categories"], "Kategori")
    units = _index(data["storage_units"], "Saklama birimi")
    tags = _index(data["tags"], "Etiket")
    items = _index(data["items"], "Ürün")
    _index(data["photos"], "Fotoğraf")
    for category in categories.values():
        if category.get("parent_ref") and category["parent_ref"] not in categories:
            raise PortableBackupError("Kategori üst kategori referansı geçersiz.")
    for item in items.values():
        required = {"name", "person_ref", "category_ref", "storage_unit_ref", "primary_color"}
        if not required.issubset(item):
            raise PortableBackupError("Ürün kaydında gerekli alanlar eksik.")
        if item["person_ref"] not in people or item["category_ref"] not in categories:
            raise PortableBackupError("Ürün kişi veya kategori referansı geçersiz.")
        if item["storage_unit_ref"] not in units:
            raise PortableBackupError("Ürün saklama birimi referansı geçersiz.")
        if any(ref not in tags for ref in item.get("tag_refs", [])):
            raise PortableBackupError("Ürün etiket referansı geçersiz.")
    required_by_section = {
        "people": {"name", "is_active"},
        "categories": {"name", "is_active", "sort_order"},
        "storage_units": {"name", "unit_type", "location_text", "is_active"},
        "tags": {"name"},
    }
    for section, required in required_by_section.items():
        if any(not required.issubset(record) for record in data[section]):
            raise PortableBackupError(f"{section} bölümünde gerekli alanlar eksik.")
    valid_statuses = {value for value, _label in Item.Status.choices}
    valid_unit_types = {value for value, _label in StorageUnit.Type.choices}
    if any(item.get("status", Item.Status.ACTIVE) not in valid_statuses for item in items.values()):
        raise PortableBackupError("Ürün durum değeri desteklenmiyor.")
    if any(unit.get("unit_type") not in valid_unit_types for unit in units.values()):
        raise PortableBackupError("Saklama birimi türü desteklenmiyor.")
    if any(photo.get("item_ref") not in items for photo in data["photos"]):
        raise PortableBackupError("Fotoğraf ürün referansı geçersiz.")


def domain_has_data():
    return any(model.objects.exists() for model in DOMAIN_MODELS)


def restore_portable_backup(validated):
    importer = IMPORTERS.get(validated.manifest["backup_format_version"])
    if not importer:
        raise PortableBackupError("Bu yedek sürümü için importer bulunamadı.")
    return importer(validated)


def import_v1(validated):
    if domain_has_data():
        raise PortableBackupError("Restore yalnızca boş bir Closet Vault envanterine yapılabilir.")
    data = validated.data
    created_files = []
    summary = {"items": 0, "photos": 0, "categories": 0, "skipped": 0, "errors": []}
    try:
        with transaction.atomic():
            people = {
                row["ref"]: Person.objects.create(
                    name=row["name"], is_active=row.get("is_active", True)
                )
                for row in data["people"]
            }
            units = {
                row["ref"]: StorageUnit.objects.create(
                    name=row["name"],
                    unit_type=row["unit_type"],
                    location_text=row["location_text"],
                    description=row.get("description", ""),
                    is_active=row.get("is_active", True),
                )
                for row in data["storage_units"]
            }
            tags = {
                row["ref"]: Tag.objects.create(name=row["name"], slug=row.get("slug", ""))
                for row in data["tags"]
            }
            categories = {}
            pending = list(data["categories"])
            while pending:
                progressed = False
                for row in pending[:]:
                    parent_ref = row.get("parent_ref")
                    if parent_ref and parent_ref not in categories:
                        continue
                    categories[row["ref"]] = Category.objects.create(
                        name=row["name"],
                        parent=categories.get(parent_ref),
                        is_active=row.get("is_active", True),
                        sort_order=row.get("sort_order", 0),
                    )
                    pending.remove(row)
                    progressed = True
                if not progressed:
                    raise PortableBackupError("Kategori hiyerarşisi döngü içeriyor.")
            summary["categories"] = len(categories)
            items = {}
            item_fields = (
                "brand",
                "model",
                "primary_color",
                "secondary_color",
                "size",
                "waist_size",
                "inseam_size",
                "shoe_size",
                "material",
                "pattern",
                "fit",
                "season",
                "status",
                "notes",
                "archived_at",
            )
            for row in data["items"]:
                values = {field: row.get(field) or "" for field in item_fields}
                values["archived_at"] = row.get("archived_at")
                values["status"] = row.get("status", Item.Status.ACTIVE)
                item = Item.objects.create(
                    name=row["name"],
                    person=people[row["person_ref"]],
                    category=categories[row["category_ref"]],
                    storage_unit=units[row["storage_unit_ref"]],
                    **values,
                )
                item.tags.set(tags[ref] for ref in row.get("tag_refs", []))
                items[row["ref"]] = item
            summary["items"] = len(items)
            for row in sorted(
                data["photos"],
                key=lambda value: (value["item_ref"], value.get("sort_order", 0), value["ref"]),
            ):
                content = validated.media[row["media_path"]]
                photo = Photo.objects.create(
                    item=items[row["item_ref"]],
                    image=ContentFile(content, name=Path(row["media_path"]).name),
                    is_cover=row.get("is_cover", False),
                    sort_order=row.get("sort_order", 0),
                )
                created_files.append(photo.image.name)
                if photo.thumbnail:
                    created_files.append(photo.thumbnail.name)
                summary["photos"] += 1
    except Exception:
        storage = Photo._meta.get_field("image").storage
        for name in created_files:
            storage.delete(name)
        raise
    return summary


IMPORTERS = {BACKUP_FORMAT_VERSION: import_v1}


def stage_uploaded_backup(upload):
    validated = validate_portable_backup(upload)
    directory = Path(tempfile.gettempdir()) / "closet-vault-portable-backups"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    cutoff = time.time() - 60 * 60
    for stale_path in directory.glob("*.zip"):
        try:
            if stale_path.stat().st_mtime < cutoff:
                stale_path.unlink()
        except OSError:
            continue
    path = directory / f"{os.urandom(16).hex()}.zip"
    upload.seek(0)
    path.write_bytes(upload.read())
    return path, validated


def cleanup_staged_backup(path):
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
