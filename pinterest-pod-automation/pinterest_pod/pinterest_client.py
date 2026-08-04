"""Pinterest API v5 istemcisi: OAuth token yenileme, pano listesi, pin oluşturma.

Notlar (2026 itibarıyla araştırılan güncel durum):
  * Pinterest API v5, OAuth 2.0 kullanır. Yeni oluşturulan uygulamalar
    otomatik olarak "Trial" erişim seviyesindedir: tüm endpoint'ler için
    günde 1000 istek limiti + endpoint kategorisine göre ek limitler.
    Bu proje günde birkaç pin paylaştığı için Trial erişimi fazlasıyla
    yeterlidir; "Standard" erişime yükseltmek (video kanıt + manuel
    Pinterest incelemesi gerektirir) bu kullanım senaryosu için GEREKLİ
    DEĞİLDİR.
  * Access token'lar ~30 gün, "continuous" refresh token'lar 60 gün
    geçerlidir ve HER kullanıldığında süresi 60 gün daha uzar; Pinterest
    her yenilemede yeni bir refresh_token da döndürebilir (rotasyon).
    Bu yüzden script, aldığı en güncel refresh_token'ı state/token_cache.json
    içinde saklar ve sonraki çalıştırmalarda onu kullanır. .env'deki
    PINTEREST_REFRESH_TOKEN sadece ilk kurulumda "tohum" değer olarak
    kullanılır (bkz. authorize.py ve README).
  * Pin oluşturma: POST /v5/pins — yerel bir görsel dosyası base64 olarak
    gönderilebildiği için (media_source.source_type = "image_base64")
    görselleri herhangi bir yere yüklemeye/host etmeye gerek yoktur.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path

import requests

API_BASE = "https://api.pinterest.com/v5"
TOKEN_URL = f"{API_BASE}/oauth/token"
TOKEN_SAFETY_MARGIN_SECONDS = 300  # süresi dolmadan 5 dk önce yenile

logger = logging.getLogger("pinterest_pod")


class PinterestError(Exception):
    """Pinterest API ile ilgili tüm hatalar için temel sınıf."""


class PinterestAuthError(PinterestError):
    """Token yenileme başarısız oldu; script sessizce devam ETMEMELİ."""


class PinterestRateLimitError(PinterestError):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class PinterestApiError(PinterestError):
    def __init__(self, message: str, status_code: int | None = None, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class PinterestClient:
    def __init__(self, app_id: str, app_secret: str, refresh_token: str, token_cache_path: Path):
        if not app_id or not app_secret:
            raise PinterestAuthError(
                "PINTEREST_APP_ID / PINTEREST_APP_SECRET .env içinde tanımlı değil."
            )
        self.app_id = app_id
        self.app_secret = app_secret
        self.bootstrap_refresh_token = refresh_token
        self.token_cache_path = token_cache_path
        self._session = requests.Session()
        self._access_token: str | None = None
        self._access_token_expires_at: float = 0

    # -- Token yönetimi -----------------------------------------------

    def _load_cache(self) -> dict:
        if self.token_cache_path.exists():
            try:
                return json.loads(self.token_cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("token_cache.json okunamadı, sıfırdan başlanacak.")
        return {}

    def _save_cache(self, cache: dict) -> None:
        self.token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    def _current_refresh_token(self) -> str:
        cache = self._load_cache()
        return cache.get("refresh_token") or self.bootstrap_refresh_token

    def _refresh_access_token(self) -> str:
        refresh_token = self._current_refresh_token()
        if not refresh_token:
            raise PinterestAuthError(
                "PINTEREST_REFRESH_TOKEN bulunamadı. Önce `python authorize.py` "
                "çalıştırarak Pinterest hesabınızla yetkilendirme yapın."
            )

        auth = (self.app_id, self.app_secret)
        data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        resp = self._session.post(TOKEN_URL, data=data, auth=auth, timeout=30)

        if resp.status_code != 200:
            raise PinterestAuthError(
                "Pinterest access token yenilenemedi (refresh_token geçersiz/süresi "
                f"dolmuş olabilir). HTTP {resp.status_code}: {resp.text}\n"
                "Çözüm: `python authorize.py` ile yeniden yetkilendirme yapın."
            )

        payload = resp.json()
        access_token = payload["access_token"]
        expires_in = payload.get("expires_in", 2592000)
        new_refresh_token = payload.get("refresh_token", refresh_token)

        cache = {
            "refresh_token": new_refresh_token,
            "access_token": access_token,
            "access_token_expires_at": time.time() + expires_in,
        }
        self._save_cache(cache)

        self._access_token = access_token
        self._access_token_expires_at = cache["access_token_expires_at"]
        return access_token

    def _get_access_token(self) -> str:
        if self._access_token is None:
            cache = self._load_cache()
            self._access_token = cache.get("access_token")
            self._access_token_expires_at = cache.get("access_token_expires_at", 0)

        if (
            not self._access_token
            or time.time() > self._access_token_expires_at - TOKEN_SAFETY_MARGIN_SECONDS
        ):
            return self._refresh_access_token()
        return self._access_token

    # -- HTTP yardımcıları ---------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        token = self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        url = f"{API_BASE}{path}"
        resp = self._session.request(method, url, headers=headers, timeout=60, **kwargs)

        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            raise PinterestRateLimitError(
                f"Pinterest hız limiti aşıldı (429): {resp.text}",
                retry_after=float(retry_after) if retry_after else None,
            )
        if resp.status_code == 401:
            # Token geçersiz olabilir; bir kez daha zorla yenileyip dene.
            self._access_token = None
            self._access_token_expires_at = 0
            token = self._refresh_access_token()
            headers["Authorization"] = f"Bearer {token}"
            resp = self._session.request(method, url, headers=headers, timeout=60, **kwargs)

        if resp.status_code >= 400:
            raise PinterestApiError(
                f"Pinterest API hatası ({method} {path}): HTTP {resp.status_code}",
                status_code=resp.status_code,
                body=resp.text,
            )
        return resp

    # -- Genel amaçlı API çağrıları --------------------------------------

    def list_boards(self) -> dict[str, str]:
        """{pano_adi: board_id} eşlemesini döner (sayfalama dahil)."""
        boards: dict[str, str] = {}
        bookmark = None
        while True:
            params = {"page_size": 100}
            if bookmark:
                params["bookmark"] = bookmark
            resp = self._request("GET", "/boards", params=params)
            payload = resp.json()
            for item in payload.get("items", []):
                boards[item["name"]] = item["id"]
            bookmark = payload.get("bookmark")
            if not bookmark:
                break
        return boards

    def create_pin(
        self,
        board_id: str,
        title: str,
        description: str,
        link: str,
        image_path: Path,
    ) -> str:
        """Pin oluşturur, Pinterest'in verdiği pin id'sini döner."""
        image_bytes = Path(image_path).read_bytes()
        body = {
            "board_id": board_id,
            "title": title[:100],
            "description": description[:800],
            "link": link,
            "media_source": {
                "source_type": "image_base64",
                "content_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        }
        resp = self._request("POST", "/pins", json=body)
        return resp.json()["id"]
