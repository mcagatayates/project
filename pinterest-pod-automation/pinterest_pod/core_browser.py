"""core.py ile aynı akış, ama Pinterest API'si yerine tarayıcı otomasyonu
(pinterest_browser_client.py) kullanır. Bkz. o modülün başındaki uyarılar.

CSV okuma, görsel üretimi, paylaşım aralığı/günlük limit mantığı core.py
ile birebir aynıdır; farkı sadece "poster" (nasıl paylaşıldığı) kısmıdır.
"""
from __future__ import annotations

import logging
from datetime import datetime

from . import csv_store, state
from .config import Config
from .content import build_description, build_title
from .image_generator import ImageGenerationError, generate_pin_image
from .pinterest_browser_client import (
    BrowserPosterError,
    NotLoggedInError,
    PinterestBrowserClient,
)
from .state import minutes_since_last_post, today_count

logger = logging.getLogger("pinterest_pod")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def run_once(config: Config) -> None:
    posting_state = state.load(config.posting_state_path)

    remaining_today = config.daily_pin_limit - today_count(posting_state)
    if remaining_today <= 0:
        logger.info(
            "Günlük paylaşım limiti (%s) doldu, bu çalıştırma atlanıyor.",
            config.daily_pin_limit,
        )
        return

    since_last = minutes_since_last_post(posting_state)
    if since_last is not None and since_last < config.min_minutes_between_pins:
        wait_left = config.min_minutes_between_pins - since_last
        logger.info(
            "Son paylaşımdan bu yana %.0f dk geçti, minimum %s dk gerekiyor "
            "(%.0f dk sonra tekrar denenebilir). Atlanıyor.",
            since_last,
            config.min_minutes_between_pins,
            wait_left,
        )
        return

    try:
        rows, fieldnames = csv_store.read_rows(config.csv_path)
    except csv_store.CsvFormatError as exc:
        logger.error("CSV okunamadı: %s", exc)
        return

    pending = csv_store.get_pending(rows)
    if not pending:
        logger.info("Bekleyen (durum=bekliyor) ürün yok.")
        return

    client = PinterestBrowserClient(
        profile_dir=config.browser_profile_dir,
        headless=config.browser_headless,
        manual_confirm=config.browser_manual_confirm,
        slow_mo_ms=config.browser_slowmo_ms,
    )

    csv_dirty = False
    posted = False

    for index, row in pending:
        urun_adi = row.get("urun_adi", "")
        pano_adi = row.get("pano_adi", "")
        design_source = row.get("tasarim_gorseli_yolu", "")
        etsy_link = row.get("etsy_link", "")

        def mark_error(message: str) -> None:
            nonlocal csv_dirty
            logger.error("[%s] %s", urun_adi or f"satır {index + 2}", message)
            rows[index]["durum"] = csv_store.ERROR_STATUS
            rows[index]["hata"] = message
            rows[index]["son_deneme"] = _now_iso()
            csv_dirty = True

        if not urun_adi or not design_source or not etsy_link or not pano_adi:
            mark_error(
                "Zorunlu alan(lar) eksik (urun_adi/tasarim_gorseli_yolu/"
                "etsy_link/pano_adi)."
            )
            continue

        try:
            image_path = generate_pin_image(
                design_source=design_source,
                urun_adi=urun_adi,
                brand_name=config.brand_name,
                output_dir=config.output_dir,
                font_path=config.font_path,
                logo_path=config.logo_path,
                filename_hint=etsy_link or urun_adi,
            )
        except ImageGenerationError as exc:
            mark_error(f"Görsel üretilemedi: {exc}")
            continue

        title = build_title(urun_adi)
        description = build_description(
            urun_adi, row.get("anahtar_kelimeler", ""), row.get("aciklama", "")
        )

        try:
            pin_url = client.create_pin(
                board_name=pano_adi,
                title=title,
                description=description,
                link=etsy_link,
                image_path=image_path,
            )
        except NotLoggedInError as exc:
            logger.error("Pinterest oturumu geçersiz: %s", exc)
            break
        except BrowserPosterError as exc:
            mark_error(f"Tarayıcı otomasyonu hatası: {exc}")
            continue

        rows[index]["durum"] = csv_store.POSTED_STATUS
        rows[index]["pin_id"] = pin_url
        rows[index]["son_deneme"] = _now_iso()
        rows[index]["hata"] = ""
        csv_dirty = True
        posted = True
        logger.info("Paylaşıldı: '%s' -> %s, pano='%s'", urun_adi, pin_url, pano_adi)
        break  # bu çalıştırmada sadece bir pin paylaş

    if csv_dirty:
        csv_store.write_rows(config.csv_path, rows, fieldnames)

    if posted:
        state.save(config.posting_state_path, state.record_post(posting_state))
    elif not csv_dirty:
        logger.info("Bu çalıştırmada işlenecek uygun ürün bulunamadı.")
