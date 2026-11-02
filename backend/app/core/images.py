"""Profile pictures: any common image becomes a small square JPEG."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

AVATAR_SIZE = 256


class NotAnImageError(ValueError):
    pass


def square_avatar(data: bytes) -> bytes:
    """Crops the middle square, scales it to 256 px and returns a JPEG."""
    try:
        opened = Image.open(io.BytesIO(data))
        opened.load()
    except (UnidentifiedImageError, OSError):
        raise NotAnImageError("That file isn't a picture we can read") from None
    upright = ImageOps.exif_transpose(opened).convert("RGB")  # phone photos come rotated
    image = ImageOps.fit(upright, (AVATAR_SIZE, AVATAR_SIZE))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85, optimize=True)
    return out.getvalue()
