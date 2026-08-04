"""Tek bir çalıştırmada en fazla bir pin paylaşan ana akış (pipeline).

Cron/Task Scheduler tarafından periyodik olarak (ör. her saat) çağrılmak
üzere tasarlanmıştır: her çağrıda paylaşım aralığı (MIN_MINUTES_BETWEEN_PINS)
ve günlük limit (DAILY_PIN_LIMIT) kontrol edilir, uygunsa bekleyen ürünler
sırayla denenir ve ilk başarılı olan paylaşılıp CSV güncellenerek çıkılır.
"""
from __future__ import annotations

import logging

from . import csv_store, state
from .config import Config
from .content import build_description, build_title
from .image_generator import ImageGenerationError, generate_pin_image
from .pinterest_client import (
    PinterestApiError,
    PinterestAuthError,
    PinterestClient,
    PinterestRateLimitError,
)
from .state import minutes_since_last_post, today_count

logger = logging.getLogger("pinterest_pod")


def _now_iso() -> str:
    from datetime import datetime

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

    try:
        client = PinterestClient(
            app_id=config.app_id,
            app_secret=config.app_secret,
            refresh_token=config.refresh_token,
            token_cache_path=config.token_cache_path,
        )
        boards = client.list_boards()
    except PinterestAuthError as exc:
        logger.error("Pinterest kimlik doğrulama hatası: %s", exc)
        return

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

        board_id = boards.get(pano_adi)
        if not board_id:
            mark_error(
                f"Pinterest'te '{pano_adi}' adında bir pano bulunamadı. "
                f"Mevcut panolar: {', '.join(sorted(boards)) or '(hiç yok)'}"
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
            pin_id = client.create_pin(
                board_id=board_id,
                title=title,
                description=description,
                link=etsy_link,
                image_path=image_path,
            )
        except PinterestRateLimitError as exc:
            logger.warning(
                "Pinterest hız limitine takıldık, bu çalıştırma durduruluyor: %s",
                exc,
            )
            break
        except PinterestAuthError as exc:
            logger.error("Pinterest kimlik doğrulama hatası: %s", exc)
            break
        except PinterestApiError as exc:
            mark_error(f"Pinterest API hatası: {exc} — gövde: {exc.body[:300]}")
            continue

        rows[index]["durum"] = csv_store.POSTED_STATUS
        rows[index]["pin_id"] = pin_id
        rows[index]["son_deneme"] = _now_iso()
        rows[index]["hata"] = ""
        csv_dirty = True
        posted = True
        logger.info("Paylaşıldı: '%s' -> pin_id=%s, pano='%s'", urun_adi, pin_id, pano_adi)
        break  # bu çalıştırmada sadece bir pin paylaş (aralık/limit kontrolü için)

    if csv_dirty:
        csv_store.write_rows(config.csv_path, rows, fieldnames)

    if posted:
        state.save(config.posting_state_path, state.record_post(posting_state))
    elif not csv_dirty:
        logger.info("Bu çalıştırmada işlenecek uygun ürün bulunamadı.")
