"""Boş bırakılan açıklamalar için basit, şablon tabanlı üretim.

Bu bir AI/otomatik metin üretimi değildir (bütçe/servis gerektirmemesi için
bilinçli olarak basit tutulmuştur) — CSV'deki `urun_adi` ve
`anahtar_kelimeler` kolonlarından okunabilir bir Pinterest açıklaması
üretir. İleride bir LLM ile geliştirilmeye açıktır.
"""
from __future__ import annotations


def build_description(urun_adi: str, anahtar_kelimeler: str, aciklama: str = "") -> str:
    if aciklama.strip():
        return aciklama.strip()

    keywords = [k.strip() for k in anahtar_kelimeler.split(",") if k.strip()]
    base = f"{urun_adi} — evinize/ofisinize şıklık katacak POD duvar sanatı tablosu."
    if keywords:
        base += " " + ", ".join(keywords) + " temalı tasarım."
        hashtags = " ".join(f"#{k.replace(' ', '')}" for k in keywords[:8])
        base += f"\n\n{hashtags}"
    return base


def build_title(urun_adi: str) -> str:
    return urun_adi.strip()
