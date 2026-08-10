# Pinterest POD Otomasyonu

Etsy'de sattığınız POD (print-on-demand) tablo/duvar sanatı ürünleri için,
elle doldurduğunuz bir CSV'den otomatik pin görseli üretip Pinterest'e
zamanlanmış şekilde paylaşan, tamamen yerel/ücretsiz bir MVP.

## İki mod

Proje iki bağımsız paylaşım moduyla gelir; CSV okuma ve görsel üretimi
(`urunler.csv`, `image_generator.py`) her iki modda da ortaktır, farkları
sadece pin'in Pinterest'e nasıl gönderildiğidir:

| | **API modu** (önerilen, mümkünse) | **Tarayıcı modu** (API'siz) |
|---|---|---|
| Kullanılan | `main.py` / `scheduler_loop.py` | `main_browser.py` |
| Nasıl paylaşır | Pinterest'in resmi API v5'i (OAuth) | Playwright ile pinterest.com arayüzünü otomatikleştirir |
| Kurulum | `authorize.py` (OAuth) | `login_setup.py` (tarayıcıda elle giriş) |
| Risk | Düşük — resmi, desteklenen yol | **Hesap kısıtlanma riski** — Kullanım Şartları'na aykırı olabilir |
| Ne zaman kullanılır | Pinterest Developer başvurunuz onaylandıysa | API erişimi alamadıysanız |

Pinterest API erişimi alamıyorsanız (developer başvurusu reddedildi/
onaylanmadı), **Tarayıcı Modu** bölümüne geçin.

## Nasıl çalışır (özet)

1. Siz `urunler.csv` dosyasına yeni ürünleri satır olarak eklersiniz
   (`durum` alanı `bekliyor` kalır).
2. `main.py`, cron/Task Scheduler tarafından periyodik olarak çalıştırılır.
   Her çalıştırmada: paylaşım aralığı ve günlük limit uygunsa, bekleyen
   ilk geçerli ürünü alır → Pillow ile dikey pin görseli üretir →
   Pinterest API'ye pin olarak gönderir → CSV'de `durum`'u `paylasildi`
   yapar → `log.txt`'e yazar.
3. Aynı anda en fazla bir pin paylaşılır; böylece `DAILY_PIN_LIMIT` ve
   `MIN_MINUTES_BETWEEN_PINS` ile paylaşımlar günün içine yayılır.

---

# Mod 1: Pinterest API (önerilen)

## Pinterest API — 2026 araştırma özeti

- API v5, OAuth 2.0 tabanlıdır. developers.pinterest.com üzerinde bir
  uygulama oluşturduğunuzda otomatik olarak **Trial erişim** verilir:
  tüm uygulama genelinde **günde 1000 istek** üst sınırı + endpoint
  kategorisine göre ek (daha düşük) limitler.
- **Standard erişime** yükseltmek manuel Pinterest incelemesi ve OAuth
  akışını gösteren bir video kaydı gerektirir; bu, üçüncü taraf
  kullanıcılara servis sunan uygulamalar içindir. **Bu proje için buna
  gerek yok**: günde 3-5 pin, Trial'ın 1000/gün limitinin çok altında.
- OAuth kapsamları (scope): `boards:read`, `pins:read`, `pins:write`.
- Access token ömrü ~30 gün. Refresh token "continuous" tiptedir: 60 gün
  geçerlidir ve her kullanıldığında süresi yeniden 60 güne uzar; Pinterest
  yenileme sırasında farklı bir refresh_token da döndürebilir (rotasyon).
  Bu yüzden script, en güncel refresh_token'ı `state/token_cache.json`
  içinde kendisi takip eder — script en az 60 günde bir çalıştığı sürece
  yeniden yetkilendirme gerekmez.
- Pin oluşturma: `POST /v5/pins`. Görseli herhangi bir yere yüklemenize
  gerek yok; Pillow ile üretilen PNG dosyası base64 olarak doğrudan
  istekle gönderilir (`media_source.source_type = "image_base64"`).
- Kaynaklar: [Pinterest Developers – Access tiers](https://developers.pinterest.com/docs/getting-started/access-tiers/),
  [Rate limits](https://developers.pinterest.com/docs/reference/rate-limits/),
  [Create boards and pins](https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/).

## Kurulum

```bash
cd pinterest-pod-automation
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 1) Pinterest Developer uygulaması oluşturun

1. [developers.pinterest.com](https://developers.pinterest.com) üzerinden
   giriş yapıp yeni bir uygulama oluşturun.
2. Uygulama ayarlarından bir **redirect URI** tanımlayın (gerçek bir sunucu
   olması gerekmez, örn. `https://localhost/callback`).
3. Uygulamanın **App ID** ve **App secret**'ını `.env` dosyasındaki
   `PINTEREST_APP_ID` / `PINTEREST_APP_SECRET` alanlarına, redirect URI'yi
   `PINTEREST_REDIRECT_URI` alanına girin.

### 2) Hesabınızla yetkilendirme yapın (tek seferlik)

```bash
python authorize.py
```

Ekrandaki adresi tarayıcıda açıp Pinterest hesabınızla onaylayın,
yönlendirildiğiniz (hata verse de sorun değil) adresi kopyalayıp terminale
yapıştırın. Script `state/token_cache.json` dosyasını otomatik oluşturur;
isterseniz ekrana basılan `refresh_token`'ı `.env`'e de yedek olarak
kaydedebilirsiniz.

### 3) Pinterest panolarınızı oluşturun

`urunler.csv`'deki `pano_adi` değerleri, Pinterest hesabınızda **zaten var
olan** pano adlarıyla birebir eşleşmelidir (script pano oluşturmaz, sadece
mevcut panolara pin ekler). Panoları Pinterest uygulamasından/sitesinden
elle oluşturun.

### 4) Marka ayarları

`.env` içindeki `BRAND_NAME` ve isteğe bağlı `LOGO_PATH` / `FONT_PATH`
alanlarını doldurun.

## CSV formatı (`urunler.csv`) — her iki modda da ortak

| Kolon | Zorunlu | Açıklama |
|---|---|---|
| `urun_adi` | evet | Pin başlığı ve görseldeki metin olarak kullanılır |
| `tasarim_gorseli_yolu` | evet | Yerel dosya yolu (proje köküne göre veya mutlak) ya da `http(s)://` URL |
| `etsy_link` | evet | Pin'in yönlendireceği Etsy ürün linki |
| `aciklama` | hayır | Boşsa `urun_adi` + `anahtar_kelimeler`'den basit bir açıklama otomatik üretilir |
| `anahtar_kelimeler` | hayır | Virgülle ayrılmış; açıklamaya ve hashtag'lere dahil edilir |
| `pano_adi` | evet | Pinterest'te var olan pano adıyla birebir aynı olmalı |
| `durum` | script yönetir | `bekliyor` / `paylasildi` / `hata` |
| `pin_id`, `son_deneme`, `hata` | script yönetir | İzlenebilirlik için otomatik doldurulur, elle dokunmanıza gerek yok |

`urunler.example.csv` dosyasında doldurulmuş örnek satırlar var; kopyalayıp
üzerine yazabilirsiniz: `cp urunler.example.csv urunler.csv`.

Bir satır `hata` durumuna düşerse (`hata` kolonuna sebep yazılır), sorunu
düzeltip `durum`'u tekrar `bekliyor` yaparak yeniden denetebilirsiniz —
script aynı satırı sonsuz döngüde tekrar tekrar denemez.

## Pin görseli üretimi — her iki modda da ortak

`tasarim_gorseli_yolu`'ndaki ham görsel, 1000×1500 px (2:3, Pinterest'in
önerdiği dikey oran) bir tuval üzerine ortalanır; altta sabit bir bantta
ürün adı ve marka adı/logosu yazılır. Üretilen görseller `pinler/` klasörüne,
her ürün için tekil bir dosya adıyla kaydedilir ve **tekrar üretilmez**
(idempotent) — aynı ürünü yeniden oluşturmak isterseniz dosyayı `pinler/`
içinden silmeniz yeterli.

## Çalıştırma: cron/Task Scheduler mı, sürekli çalışan döngü mü?

**Önerilen: cron (Linux/macOS) veya Task Scheduler (Windows).** `main.py`
her çağrıldığında tek bir kontrol yapıp (gerekirse tek bir pin paylaşıp)
çıkar; tüm durum CSV ve `state/` dosyalarında tutulur. Bunun `schedule`
kütüphanesiyle yazılmış sonsuz döngüye göre avantajı: bilgisayar/sunucu
yeniden başlarsa, uykuya geçerse ya da process çökerse, işletim sistemi
zamanlayıcısı bir sonraki tetiklemede işi otomatik devam ettirir — sürekli
açık bir process'e ve onu hayatta tutmaya (tmux/screen/servis) güvenmeniz
gerekmez. Sık çağırmak zararsızdır çünkü aralık/limit kontrolü script
içinde zaten yapılır.

**Linux/macOS (crontab -e), her saat başı kontrol:**
```
0 * * * * cd /tam/yol/pinterest-pod-automation && /tam/yol/venv/bin/python main.py
```

**Windows Task Scheduler:** Yeni bir görev oluşturup "Program/script" olarak
`venv\Scripts\python.exe`, "Arguments" olarak `main.py`, "Start in" olarak
proje klasörünü girin; tetikleyiciyi "her saat tekrarla" şeklinde ayarlayın.

**Alternatif — sürekli açık bir makineniz varsa ve cron kurmak
istemiyorsanız:**
```bash
python scheduler_loop.py
```
Bu, aynı mantığı 30 dakikada bir kontrol eden bir `schedule` döngüsüyle
çalıştırır; terminali açık tutmanız (veya `tmux`/`nohup`/sistem servisi
olarak arka planda çalıştırmanız) gerekir.

## Loglama

Tüm çalıştırmalar `log.txt`'e (2 MB'ta bir döner, 3 yedek tutulur) ve
konsola yazılır: hangi ürün ne zaman paylaşıldı, hangi hatalar oluştu.
Kimlik doğrulama hataları (`refresh_token` süresi dolmuş vb.) veya
Pinterest API hataları **sessizce yutulmaz**, `log.txt`'e açıkça yazılır
ve `main.py` hata koduyla (`exit 1`) çıkar — cron bunu genelde e-posta ile
size bildirir (`crontab` ayarlarınıza bağlı).

## Riskler ve sınırlamalar (Mod 1 — API)

- Pinterest'in hız limitlerine (`429`) takılırsanız script o çalıştırmayı
  sessizce atlamaz, `log.txt`'e uyarı yazıp satırı `bekliyor` bırakır;
  bir sonraki çalıştırmada tekrar dener.
- `pano_adi` Pinterest'teki panolarla eşleşmezse satır `hata` durumuna
  geçer, script çökmez, diğer bekleyen ürünlere geçer.
- `DAILY_PIN_LIMIT` ve `MIN_MINUTES_BETWEEN_PINS` değerlerini agresif
  düşürmeyin; Pinterest'in spam/otomasyon politikalarına takılıp hesabınız
  kısıtlanabilir.

---

# Mod 2: Tarayıcı Modu (API'siz)

## ⚠️ Önce bunu okuyun

Pinterest Developer başvurunuz onaylanmadıysa/API alamıyorsanız, bu mod
`pinterest.com` web arayüzünü bir tarayıcı ile (Playwright) **insan gibi
kullanarak** aynı işi yapar: giriş yapar, pin oluşturma formunu doldurur,
yayınlar.

**Bunun bedelleri var:**

- Pinterest'in resmi API'si değildir; bu **Kullanım Şartları'na aykırı
  olabilir** ve hesabınızın (Etsy pazarlamanız için kullandığınız hesap)
  kısıtlanması/askıya alınması riski taşır. Kendi sorumluluğunuzda,
  düşük hacimde (günde 3-5 pin, insan temposunda gecikmelerle) kullanın.
- pinterest.com arayüzü Pinterest tarafından önceden haber verilmeden
  değiştirilebilir; script'in kullandığı seçiciler (`SELECTORS` sözlüğü,
  `pinterest_pod/pinterest_browser_client.py`) o zaman bozulur ve
  güncellenmesi gerekir. Bu seçiciler bu ortamda gerçek bir Pinterest
  hesabına erişim olmadığı için **canlı Pinterest'e karşı test
  edilememiştir** — sadece Playwright'ın genel mekaniği (form doldurma,
  dosya yükleme, hata/ekran görüntüsü akışı) yerel bir sahte formla
  doğrulanmıştır. İlk gerçek çalıştırmalarınızı mutlaka aşağıdaki "güvenli
  ilk çalıştırma" ayarlarıyla yapın.
- Parola yerine tarayıcı oturumu (çerezler) yerel diskte saklanır
  (`state/browser_profile/`) — bu klasörü kimseyle paylaşmayın, `.env`
  gibi git'e commitlenmez.

## Kurulum (Mod 2)

```bash
cd pinterest-pod-automation
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium   # bir kez, tarayıcı motorunu indirir
cp .env.example .env          # zaten yapmadıysanız
```

### 1) Bir kez giriş yapın

```bash
python login_setup.py
```

Açılan tarayıcı penceresinde Pinterest hesabınızla normal şekilde giriş
yapın (2FA/captcha varsa çözün), sonra terminale dönüp Enter'a basın.
Oturum `state/browser_profile/` içine kaydedilir ve sonraki çalıştırmalarda
tekrar giriş istemeden kullanılır (Pinterest sizi çıkışa zorlayana kadar).

### 2) Panolarınızı oluşturun

Mod 1'deki gibi: `urunler.csv`'deki `pano_adi` değerleri Pinterest
hesabınızda zaten var olan pano adlarıyla birebir eşleşmelidir.

### 3) "Güvenli ilk çalıştırma" ayarları (önerilir)

`.env` içinde varsayılan olarak zaten şu ayarlarla gelir:

```
BROWSER_HEADLESS=false        # tarayıcı penceresini görürsünüz
BROWSER_MANUAL_CONFIRM=true   # form dolduktan sonra siz Enter'a basmadan yayınlanmaz
```

İlk birkaç çalıştırmayı böyle yapıp formun doğru dolduğunu gözünüzle
doğrulayın. Güvendikten sonra `BROWSER_HEADLESS=true` ve
`BROWSER_MANUAL_CONFIRM=false` yaparak tam otomatik/arka planda
çalıştırabilirsiniz — ama yine de düşük hacimde kalın.

### 4) Çalıştırma

```bash
python main_browser.py
```

Aynı `DAILY_PIN_LIMIT` / `MIN_MINUTES_BETWEEN_PINS` mantığıyla cron/Task
Scheduler'a bağlayabilirsiniz (bkz. yukarıdaki "Çalıştırma" bölümü,
`main.py` yerine `main_browser.py` kullanın).

## Bir adım bozulursa (seçici hatası)

Hata mesajı hangi adımda (`görsel yükleme`, `başlık alanı`, `pano seçimi`,
`yayınlama` vb.) takıldığını söyler ve `state/debug_screenshots/` içine o
anki ekran görüntüsünü kaydeder. `pinterest_pod/pinterest_browser_client.py`
dosyasının başındaki `SELECTORS` sözlüğünde ilgili satırı, ekran
görüntüsüne bakarak güncel Pinterest arayüzüne göre düzeltmeniz yeterlidir.

## Riskler ve sınırlamalar (Mod 2 — Tarayıcı)

- Yukarıdaki "Önce bunu okuyun" bölümündeki hesap kısıtlanma riski
  geçerlidir.
- Pano bulunamazsa/form elemanı değişmişse satır `hata` durumuna geçer,
  script çökmez, diğer bekleyen ürünlere geçer (Mod 1 ile aynı davranış).
- Oturum süresi dolarsa (`NotLoggedInError`) script açıkça hata verir;
  `python login_setup.py`'yi tekrar çalıştırmanız gerekir.
- `DAILY_PIN_LIMIT` ve `MIN_MINUTES_BETWEEN_PINS`'i Mod 1'den daha da
  temkinli tutun; bu mod bot tespiti açısından daha risklidir.

---

## Kapsam dışı (bu MVP'de yok)

- Etsy API entegrasyonu (ürünler CSV'den elle girilir).
- Gelişmiş/estetik pin şablonlama (şu an tek şablon: tasarım + alt bant).
- Çoklu Pinterest hesabı desteği.
