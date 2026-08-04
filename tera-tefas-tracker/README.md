# Tera TEFAS Tracker

Tera Portföy Yönetimi A.Ş.'nin TEFAS'taki fonlarını her sabah (hafta içi,
BIST açılışından ~1 saat önce) kontrol edip Telegram'a bildirim atan bot.

## Ne yapıyor

1. **Günlük** — TEFAS'ın resmi API'sinden her Tera fonunun varlık sınıfı
   dağılımını (Hisse Senedi %, Kamu Borçlanma %, Ters Repo % vb.) çeker,
   bir önceki işlem gününe göre kıyaslar, artan kalemleri bildirir.
2. **Aylık** — KAP'ta yeni bir "Fon Portföy Dağılım Raporu" yayınlanınca
   (bu rapor ayda ~1 kez, ay kapandıktan ~6 iş günü sonra çıkar), hangi
   hisselerin (GARAN, THYAO vb.) ağırlığının arttığını bildirir.

## Bilinen sınırlama

TEFAS **günlük** olarak sadece varlık sınıfı bazında veri yayınlıyor;
hangi şirketin hissesini ne kadar tuttuğu bilgisi (per-stock) sadece
KAP'ın **aylık** raporunda var. Yani "hangi hisseyi aldılar" sorusunun
gerçek, hisse-bazlı cevabı ayda yaklaşık 1 kez güncellenir — günlük mesaj
her zaman gelir ama çoğu gün sadece varlık sınıfı trendini içerir.

KAP tarafındaki rapor ayrıştırma (parsing) mantığı, bu kodun yazıldığı
ortamdan kap.org.tr'ye erişim engelli olduğu için **canlı test edilemeden**
yazıldı. İlk birkaç gerçek çalıştırmadan sonra (Actions loglarına bakarak)
muhtemelen ince ayar gerekecek. Otomatik ayrıştırma başarısız olursa bot
çökmez — sadece "yeni rapor var ama otomatik okunamadı, işte link" der.

## Kurulum

### 1. Bu workflow'un çalışması için branch main'e alınmalı

GitHub Actions'ın `schedule` (cron) tetikleyicisi **sadece reponun
varsayılan branch'indeki** (`main`) workflow dosyasını dikkate alır. Bu
kod şu an `feature/tera-tefas-tracker` branch'inde — cron'un gerçekten
çalışması için bu branch'in main'e merge edilmesi gerekiyor.

### 2. İki secret ekle

Repo → **Settings** → **Secrets and variables** → **Actions** →
**New repository secret**:

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather'dan aldığın token |
| `TELEGRAM_CHAT_ID` | `getUpdates` ile bulduğun chat id |

### 3. Test et

Secret'lar eklendikten ve branch main'e alındıktan sonra, Actions
sekmesinden **"Tera TEFAS Daily Check"** workflow'unu bulup **"Run
workflow"** ile elle bir kere çalıştırabilirsin — sabahı beklemene gerek
yok.

## Tera fon listesi

`src/main.py` içindeki `TERA_FUNDS` sabiti şu an bilinen fonları
içeriyor (THF, FSU, TP2, TLV, T3B, TLY, TMV). Tera yeni bir fon
çıkarırsa/kapatırsa bu listeyi güncellemek gerekir —
[teraportfoy.com/fonlarimiz](https://www.teraportfoy.com/fonlarimiz)
üzerinden kontrol edilebilir.
