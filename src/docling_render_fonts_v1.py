"""Fingerprint the Linux font dependency used by official docling-parse.

The parser's system-font resolver affects the image presented to layout models.
This is build/runtime verification, never text extraction or reconstruction.
"""
from pathlib import Path
import hashlib

from src.docling_contract_v1 import DoclingError

FONT_ROOTS = (Path("/usr/share/fonts"), Path("/usr/local/share/fonts"),
              Path("/usr/share/texmf/fonts"), Path("/usr/X11R6/lib/X11/fonts"))
STANDARD_FONT = "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf"
STANDARD_FONT_SHA256 = "7c25be4d78155523080ab85b10277150657ff7dabbcad7037bdd536c9b6d0d08"


def font_inventory() -> dict[str, str]:
    files = {}
    for root in FONT_ROOTS:
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".otf", ".ttf", ".ttc", ".pfb"}:
                with path.open("rb") as stream:
                    files[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
    if files.get(STANDARD_FONT) != STANDARD_FONT_SHA256:
        raise DoclingError("docling_render_fonts_invalid")
    return files


def verify_fonts(expected: dict) -> None:
    if not expected or font_inventory() != expected:
        raise DoclingError("docling_render_fonts_invalid")
