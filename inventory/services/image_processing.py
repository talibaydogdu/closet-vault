from io import BytesIO
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


def process_image(upload, max_size=1600):
    """Validate, orient, resize and return an RGB WebP without retaining the original."""
    try:
        upload.seek(0)
        with Image.open(upload) as source:
            source.verify()
        upload.seek(0)
        with Image.open(upload) as source:
            image = ImageOps.exif_transpose(source)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")
            elif image.mode == "RGBA":
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=image.getchannel("A"))
                image = background
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, "WEBP", quality=80, method=6)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("Geçerli bir fotoğraf yükleyin.") from exc
    return ContentFile(output.getvalue(), name=f"{uuid4().hex}.webp")


def make_thumbnail(image_field, max_size=400):
    try:
        image_field.open("rb")
        with Image.open(image_field) as source:
            image = source.convert("RGB")
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, "WEBP", quality=80, method=6)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError("Thumbnail oluşturulamadı.") from exc
    return ContentFile(output.getvalue(), name=f"thumb-{Path(image_field.name).stem}.webp")
