"""Alternatif: cron/Task Scheduler kurmak istemeyenler için sürekli çalışan
tek işlemli döngü (Python `schedule` kütüphanesi ile).

DİKKAT: cron/Task Scheduler daha sağlam bir seçenektir (bkz. main.py'deki
açıklama) çünkü işletim sistemi tarafından yönetilir. Bu script'i tercih
ederseniz, terminali kapatmadan (ör. `tmux`/`screen` içinde veya
sistem servis olarak) sürekli açık tutmanız gerekir; aksi halde bilgisayar
kapanır/uyur/işlem çökerse paylaşımlar durur ve siz fark etmezsiniz.

Kullanım:
    python scheduler_loop.py
"""
from __future__ import annotations

import time

import schedule

from pinterest_pod.config import load_config
from pinterest_pod.core import run_once
from pinterest_pod.logging_setup import setup_logging

CHECK_INTERVAL_MINUTES = 30


def main() -> None:
    config = load_config()
    logger = setup_logging(config.log_path)

    def tick() -> None:
        try:
            run_once(config)
        except Exception:
            logger.exception("Beklenmeyen hata (döngü devam ediyor).")

    logger.info(
        "Zamanlayıcı döngüsü başladı, her %s dakikada bir kontrol edilecek "
        "(Ctrl+C ile durdurulur).",
        CHECK_INTERVAL_MINUTES,
    )
    tick()  # başlangıçta bir kez hemen kontrol et
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(tick)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
