"""API'siz "tarayıcı modu": Playwright ile pinterest.com arayüzünü bir
insan gibi kullanarak pin oluşturur.

ÖNEMLİ UYARILAR
----------------
* Bu, Pinterest'in resmi API'si DEĞİLDİR. pinterest.com'un web arayüzünü
  otomatikleştirir. Bu, Pinterest Kullanım Şartları'na aykırı olabilir ve
  hesabınızın kısıtlanması/askıya alınması riski taşır. Kendi
  sorumluluğunuzda, kendi hesabınızla kullanın.
* pinterest.com arayüzü Pinterest tarafından herhangi bir zamanda
  değiştirilebilir. Aşağıdaki SELECTORS sözlüğü ilk elden test
  edilememiştir (bu ortamda gerçek/oturum açık bir Pinterest hesabına
  erişim yoktur) — best-effort'tur. İlk çalıştırmaları mutlaka
  BROWSER_HEADLESS=false ve BROWSER_MANUAL_CONFIRM=true ile yapıp
  gözünüzle doğrulayın; bir adım başarısız olursa hata mesajı hangi
  adımda takıldığını söyler ve state/debug_screenshots/ altına ekran
  görüntüsü kaydedilir — sorunu SELECTORS sözlüğündeki ilgili satırı
  güncelleyerek çözebilirsiniz.
"""
from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

logger = logging.getLogger("pinterest_pod")

PIN_BUILDER_URL = "https://www.pinterest.com/pin-creation-tool/"
PIN_SUCCESS_URL_PATTERN = re.compile(r"pinterest\.[a-z.]+/pin/")
DEFAULT_TIMEOUT_MS = 20_000

# Tek bir yerden yönetilebilsin diye tüm sayfa elemanı arama mantığı burada.
# Değer, bir Page nesnesi alıp bir Locator döndüren bir fonksiyondur.
# Pinterest arayüzü değişirse önce burayı güncellemeyi deneyin.
SELECTORS = {
    "file_input": lambda page: page.locator("input[type='file']").first,
    "title_field": lambda page: page.get_by_placeholder(re.compile("title|başlık", re.I)).first,
    "description_field": lambda page: page.get_by_placeholder(
        re.compile("description|açıklama", re.I)
    ).first,
    "link_field": lambda page: page.get_by_placeholder(
        re.compile("link|website|bağlantı", re.I)
    ).first,
    "board_button": lambda page: page.get_by_role(
        "button", name=re.compile("board|pano", re.I)
    ).first,
    "board_search_input": lambda page: page.get_by_placeholder(
        re.compile("search|board|pano", re.I)
    ).first,
    "publish_button": lambda page: page.get_by_role(
        "button", name=re.compile("^(publish|yayınla)$", re.I)
    ).first,
}


class BrowserPosterError(Exception):
    pass


class NotLoggedInError(BrowserPosterError):
    pass


class PinCreationError(BrowserPosterError):
    def __init__(self, step: str, message: str, screenshot_path: Path | None = None):
        full = f"[{step}] {message}"
        if screenshot_path:
            full += f" (ekran görüntüsü: {screenshot_path})"
        super().__init__(full)
        self.step = step
        self.screenshot_path = screenshot_path


class BoardNotFoundError(PinCreationError):
    pass


def _human_pause(min_ms: int = 400, max_ms: int = 1200) -> None:
    time.sleep(random.uniform(min_ms, max_ms) / 1000)


class PinterestBrowserClient:
    def __init__(
        self,
        profile_dir: Path,
        headless: bool = True,
        manual_confirm: bool = True,
        slow_mo_ms: int = 150,
        debug_screenshot_dir: Path | None = None,
        executable_path: str | None = None,
    ):
        self.profile_dir = profile_dir
        self.headless = headless
        self.manual_confirm = manual_confirm
        self.slow_mo_ms = slow_mo_ms
        self.debug_screenshot_dir = debug_screenshot_dir or (profile_dir.parent / "debug_screenshots")
        self.executable_path = executable_path

    def _screenshot(self, page: Page, step: str) -> Path:
        self.debug_screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.debug_screenshot_dir / f"{int(time.time())}_{step}.png"
        try:
            page.screenshot(path=str(path))
        except Exception:
            logger.warning("Ekran görüntüsü alınamadı (%s).", step)
        return path

    def _find(self, page: Page, key: str):
        locator = SELECTORS[key](page)
        locator.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        return locator

    def create_pin(
        self,
        board_name: str,
        title: str,
        description: str,
        link: str,
        image_path: Path,
    ) -> str:
        """Pin'i tarayıcı üzerinden oluşturur, pin URL'ini döner."""
        if not self.profile_dir.exists():
            raise NotLoggedInError(
                "Kayıtlı bir Pinterest oturumu bulunamadı. Önce "
                "`python login_setup.py` çalıştırıp Pinterest hesabınızla "
                "giriş yapın."
            )

        with sync_playwright() as pw:
            context = pw.chromium.launch_persistent_context(
                str(self.profile_dir),
                headless=self.headless,
                slow_mo=self.slow_mo_ms,
                viewport={"width": 1400, "height": 950},
                executable_path=self.executable_path,
            )
            try:
                page = context.new_page()
                logger.info("Pin oluşturma sayfası açılıyor...")
                page.goto(PIN_BUILDER_URL, timeout=60_000)
                _human_pause()

                if "/login" in page.url or "/sso" in page.url:
                    raise NotLoggedInError(
                        "Pinterest oturumu geçersiz/süresi dolmuş görünüyor. "
                        "`python login_setup.py` ile yeniden giriş yapın."
                    )

                logger.info("Görsel yükleniyor: %s", image_path)
                try:
                    self._find(page, "file_input").set_input_files(str(image_path))
                except PlaywrightTimeoutError as exc:
                    shot = self._screenshot(page, "file_input")
                    raise PinCreationError("görsel yükleme", str(exc), shot) from exc
                _human_pause(1000, 2000)

                logger.info("Başlık yazılıyor...")
                try:
                    self._find(page, "title_field").fill(title)
                except PlaywrightTimeoutError as exc:
                    shot = self._screenshot(page, "title_field")
                    raise PinCreationError("başlık alanı", str(exc), shot) from exc
                _human_pause()

                logger.info("Açıklama yazılıyor...")
                try:
                    self._find(page, "description_field").fill(description)
                except PlaywrightTimeoutError as exc:
                    shot = self._screenshot(page, "description_field")
                    raise PinCreationError("açıklama alanı", str(exc), shot) from exc
                _human_pause()

                logger.info("Hedef link yazılıyor...")
                try:
                    self._find(page, "link_field").fill(link)
                except PlaywrightTimeoutError as exc:
                    shot = self._screenshot(page, "link_field")
                    raise PinCreationError("link alanı", str(exc), shot) from exc
                _human_pause()

                logger.info("Pano seçiliyor: %s", board_name)
                try:
                    self._find(page, "board_button").click()
                    _human_pause()
                    search = self._find(page, "board_search_input")
                    search.fill(board_name)
                    _human_pause(600, 1200)
                    option = page.get_by_role("option", name=re.compile(re.escape(board_name), re.I)).first
                    option.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
                    option.click()
                except PlaywrightTimeoutError as exc:
                    shot = self._screenshot(page, "board_select")
                    raise BoardNotFoundError(
                        "pano seçimi",
                        f"'{board_name}' adlı pano bulunamadı/seçilemedi: {exc}",
                        shot,
                    ) from exc
                _human_pause()

                if self.manual_confirm:
                    print(
                        f"\n>>> '{title}' pin'i için form dolduruldu. Tarayıcı "
                        "penceresinde kontrol edin.\n"
                        ">>> Yayınlamak için burada Enter'a basın (iptal için Ctrl+C): ",
                        end="",
                    )
                    input()

                logger.info("Yayınlanıyor...")
                try:
                    self._find(page, "publish_button").click()
                    page.wait_for_url(PIN_SUCCESS_URL_PATTERN, timeout=30_000)
                except PlaywrightTimeoutError as exc:
                    shot = self._screenshot(page, "publish")
                    raise PinCreationError("yayınlama", str(exc), shot) from exc

                pin_url = page.url
                logger.info("Pin yayınlandı: %s", pin_url)
                return pin_url
            finally:
                context.close()
