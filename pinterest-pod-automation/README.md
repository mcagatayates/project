# Pinterest POD Otomasyonu

Etsy'de sattığınız POD (print-on-demand) tablo/duvar sanatı ürünleri için,
elle doldurduğunuz bir CSV'den otomatik pin görseli üretip Pinterest'e
zamanlanmış şekilde paylaşan, tamamen yerel/ücretsiz bir MVP.

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

## CSV formatı (`urunler.csv`)

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

## Pin görseli üretimi

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

## Riskler ve sınırlamalar

- Pinterest'in hız limitlerine (`429`) takılırsanız script o çalıştırmayı
  sessizce atlamaz, `log.txt`'e uyarı yazıp satırı `bekliyor` bırakır;
  bir sonraki çalıştırmada tekrar dener.
- `pano_adi` Pinterest'teki panolarla eşleşmezse satır `hata` durumuna
  geçer, script çökmez, diğer bekleyen ürünlere geçer.
- `DAILY_PIN_LIMIT` ve `MIN_MINUTES_BETWEEN_PINS` değerlerini agresif
  düşürmeyin; Pinterest'in spam/otomasyon politikalarına takılıp hesabınız
  kısıtlanabilir.

## Kapsam dışı (bu MVP'de yok)

- Etsy API entegrasyonu (ürünler CSV'den elle girilir).
- Gelişmiş/estetik pin şablonlama (şu an tek şablon: tasarım + alt bant).
- Çoklu Pinterest hesabı desteği.
