"""Tek seferlik çalıştırma girişi — cron / Windows Task Scheduler için önerilir.

Kullanım:
    python main.py

Her çağrıda: paylaşım aralığı/günlük limit uygunsa, bekleyen ürünlerden
ilk geçerli olanı Pinterest'e paylaşır ve çıkar. Uygun değilse (limit
dolu / henüz sıra gelmedi / bekleyen ürün yok) hiçbir şey yapmadan çıkar.

Neden cron/Task Scheduler (schedule kütüphanesi yerine varsayılan)?
  - Script sürekli bellekte açık kalmıyor: bilgisayar/sunucu yeniden
    başlarsa, işlem çökerse veya uykuya geçerse `schedule` tabanlı sonsuz
    döngü sessizce durur ve siz fark etmeden günlerce pin atmaz. Cron/Task
    Scheduler işletim sistemi tarafından yönetildiği için bu risk yoktur.
  - Her çalıştırma bağımsız ve durum bilgisi (state/, CSV) dosyada
    tutulduğundan hangi mekanizmayla tetiklendiğinin önemi yok.
  - Yine de sürekli açık bir makine üzerinde tek komutla çalıştırmak
    isterseniz `scheduler_loop.py` alternatifini kullanabilirsiniz
    (bkz. README).

Örnek cron girdisi (her saat başı kontrol eder, mesafe/limit script
içinde zaten kontrol edildiği için sık çağırmak zararsızdır):
    0 * * * * cd /path/to/pinterest-pod-automation && /path/to/venv/bin/python main.py
"""
from __future__ import annotations

import sys

from pinterest_pod.config import load_config
from pinterest_pod.core import run_once
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
