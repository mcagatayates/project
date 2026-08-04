"""urunler.csv okuma / güncelleme modülü.

CSV her çalıştırmada tamamen okunur, ilgili satır bellekte güncellenir ve
dosyanın tamamı atomik olarak (geçici dosya + os.replace) geri yazılır.
Böylece yazma sırasında script kesintiye uğrarsa CSV bozulmaz.
"""
from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path
from typing import Iterable

REQUIRED_COLUMNS = [
    "urun_adi",
    "tasarim_gorseli_yolu",
    "etsy_link",
    "aciklama",
    "anahtar_kelimeler",
    "pano_adi",
    "durum",
]

# Script'in ilerlemeyi/izlenebilirliği takip etmek için otomatik ekleyip
# doldurduğu ek kolonlar. Kullanıcının bunları elle doldurması gerekmez.
BOOKKEEPING_COLUMNS = ["pin_id", "son_deneme", "hata"]

ALL_COLUMNS = REQUIRED_COLUMNS + BOOKKEEPING_COLUMNS

PENDING_STATUS = "bekliyor"
POSTED_STATUS = "paylasildi"
ERROR_STATUS = "hata"


class CsvFormatError(ValueError):
    pass


def read_rows(csv_path: Path) -> tuple[list[dict], list[str]]:
    if not csv_path.exists():
        raise CsvFormatError(f"CSV dosyası bulunamadı: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            raise CsvFormatError(
                f"CSV'de zorunlu kolon(lar) eksik: {', '.join(missing)}"
            )

        # Bookkeeping kolonlarını yoksa ekle (sona eklenir).
        fieldnames = list(fieldnames)
        for col in BOOKKEEPING_COLUMNS:
            if col not in fieldnames:
                fieldnames.append(col)

        rows = []
        for raw_row in reader:
            row = {col: (raw_row.get(col) or "").strip() for col in fieldnames}
            rows.append(row)

    return rows, fieldnames


def write_rows(csv_path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    csv_path = Path(csv_path)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{csv_path.name}.", suffix=".tmp", dir=str(csv_path.parent)
    )
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: row.get(col, "") for col in fieldnames})
        os.replace(tmp_path, csv_path)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def is_pending(row: dict) -> bool:
    durum = (row.get("durum") or "").strip().lower()
    return durum in ("", PENDING_STATUS)


def get_pending(rows: list[dict]) -> list[tuple[int, dict]]:
    """CSV'deki sırayla, durum = bekliyor (veya boş) olan satırları döner."""
    return [(i, row) for i, row in enumerate(rows) if is_pending(row)]
