"""Tarayıcı modu (API'siz) için tek seferlik Pinterest oturum açma.

Ne yapar:
  1. Görünür (headless olmayan) bir Chromium penceresi açar ve
     pinterest.com/login adresine gider.
  2. Siz o pencerede Pinterest hesabınızla normal şekilde giriş yaparsınız
     (2FA/captcha varsa onları da orada elle çözersiniz).
  3. Giriş yaptıktan sonra terminale dönüp Enter'a basarsınız; script oturumu
     (çerezler dahil) state/browser_profile/ klasörüne kalıcı olarak kaydeder.

Bu oturum süresi dolana/Pinterest sizi çıkışa zorlayana kadar
pinterest_browser_client.py tarafından tekrar tekrar kullanılır — normal
şartlarda bunu sadece bir kez çalıştırmanız yeterlidir.

Kullanım:
    python login_setup.py
"""
from __future__ import annotations

from playwright.sync_api import sync_playwright

from pinterest_pod.config import load_config

LOGIN_URL = "https://www.pinterest.com/login/"


def main() -> None:
    config = load_config()
    profile_dir = config.browser_profile_dir
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Tarayıcı profili: {profile_dir}")
    print("Görünür bir Chromium penceresi açılacak, Pinterest hesabınızla giriş yapın...\n")

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 950},
        )
        page = context.new_page()
        page.goto(LOGIN_URL, timeout=60_000)

        input(
            "Tarayıcıda Pinterest hesabınıza giriş yaptıktan (ve varsa "
            "2FA/captcha'yı çözdükten) sonra buraya dönüp Enter'a basın: "
        )

        if "/login" in page.url:
            print(
                "\nUYARI: Sayfa hâlâ giriş ekranında görünüyor. Giriş "
                "başarısız olmuş olabilir. Yine de oturum kaydedilecek, "
                "gerekirse bu script'i tekrar çalıştırın."
            )
        else:
            print("\nGiriş başarılı görünüyor, oturum kaydediliyor...")

        context.close()

    print(f"Tamamlandı. Oturum '{profile_dir}' içine kaydedildi.")
    print("Artık `python main_browser.py` ile pin paylaşımını deneyebilirsiniz.")


if __name__ == "__main__":
    main()
