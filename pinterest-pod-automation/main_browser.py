"""Tarayıcı modu (API'siz) tek seferlik çalıştırma girişi.

Ön koşul: `python login_setup.py` ile bir kez Pinterest oturumu açılmış
olmalı.

Kullanım:
    python main_browser.py

main.py (API modu) ile aynı zamanlama/loglama mantığını kullanır — cron/
Task Scheduler ile periyodik çağırmak için tasarlanmıştır. Farkı: pin'i
Pinterest API'si yerine bir tarayıcı otomasyonuyla (pinterest.com arayüzü
üzerinden) paylaşır. Riskler için pinterest_pod/pinterest_browser_client.py
başındaki notlara ve README'ye bakın.

İlk çalıştırmalarda .env içinde BROWSER_HEADLESS=false ve
BROWSER_MANUAL_CONFIRM=true bırakmanız önerilir; böylece tarayıcıyı görüp
formun doğru dolduğunu siz onayladıktan sonra yayınlanır.
"""
from __future__ import annotations

import sys

from pinterest_pod.config import load_config
from pinterest_pod.core_browser import run_once
from pinterest_pod.logging_setup import setup_logging


def main() -> int:
    config = load_config()
    logger = setup_logging(config.log_path)
    try:
        run_once(config)
    except Exception:
        logger.exception("Beklenmeyen hata, çalıştırma durduruldu.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
