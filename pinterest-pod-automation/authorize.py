"""Tek seferlik Pinterest OAuth yetkilendirme yardımcı script'i.

Ne yapar:
  1. Pinterest yetkilendirme URL'ini oluşturur ve ekrana yazar.
  2. Bu URL'i tarayıcıda açmanızı, Pinterest hesabınızla giriş yapıp
     uygulamayı onaylamanızı ister.
  3. Onaydan sonra tarayıcı, .env'deki PINTEREST_REDIRECT_URI adresine
     yönlendirilir (o adres genelde "bağlanılamıyor" hatası gösterir —
     bu normaldir). Adres çubuğundaki tam URL'i (içinde ?code=... olan)
     kopyalayıp buraya yapıştırmanız yeterlidir.
  4. Script, kodu access_token + refresh_token ile değiştirir ve
     state/token_cache.json içine kaydeder.

Kullanım:
    python authorize.py
"""
from __future__ import annotations

import sys
import webbrowser
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from pinterest_pod.config import load_config
from pinterest_pod.pinterest_client import PinterestClient, TOKEN_URL

SCOPES = "boards:read,pins:read,pins:write"
AUTH_BASE = "https://www.pinterest.com/oauth/"


def build_auth_url(app_id: str, redirect_uri: str) -> str:
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": "pinterest-pod-automation",
    }
    return f"{AUTH_BASE}?{urlencode(params)}"


def extract_code(user_input: str) -> str:
    user_input = user_input.strip()
    if user_input.startswith("http"):
        query = urlparse(user_input).query
        code = parse_qs(query).get("code", [None])[0]
        if not code:
            raise SystemExit("Yapıştırılan URL'de 'code' parametresi bulunamadı.")
        return code
    return user_input


def main() -> None:
    config = load_config()
    if not config.app_id or not config.app_secret:
        raise SystemExit(
            "Önce .env dosyasına PINTEREST_APP_ID ve PINTEREST_APP_SECRET girin "
            "(.env.example dosyasına bakın)."
        )

    auth_url = build_auth_url(config.app_id, config.redirect_uri)
    print("1) Aşağıdaki adresi tarayıcıda açın ve Pinterest hesabınızla onaylayın:\n")
    print(f"   {auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print(
        "2) Onayladıktan sonra yönlendirildiğiniz sayfanın TAM adresini "
        "(içinde ?code=... geçen) veya sadece 'code' değerini yapıştırın:"
    )
    user_input = input("> ")
    code = extract_code(user_input)

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
        },
        auth=(config.app_id, config.app_secret),
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"Token değişimi başarısız oldu: HTTP {resp.status_code}\n{resp.text}", file=sys.stderr)
        raise SystemExit(1)

    payload = resp.json()
    client = PinterestClient(
        app_id=config.app_id,
        app_secret=config.app_secret,
        refresh_token=payload["refresh_token"],
        token_cache_path=config.token_cache_path,
    )
    # Cache'i doğrudan doldurup ilk gereksiz refresh çağrısını atlıyoruz.
    client._save_cache(  # noqa: SLF001 - kasıtlı, tek seferlik kurulum script'i
        {
            "refresh_token": payload["refresh_token"],
            "access_token": payload["access_token"],
            "access_token_expires_at": __import__("time").time() + payload.get("expires_in", 2592000),
        }
    )

    print("\nYetkilendirme başarılı! state/token_cache.json güncellendi.")
    print(
        "İsteğe bağlı ama önerilir: aşağıdaki refresh_token'ı .env dosyasındaki "
        "PINTEREST_REFRESH_TOKEN alanına da yapıştırın (yedek/ilk kurulum değeri "
        "olarak kullanılır):\n"
    )
    print(f"PINTEREST_REFRESH_TOKEN={payload['refresh_token']}")


if __name__ == "__main__":
    main()
