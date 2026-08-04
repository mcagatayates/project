# Tera TEFAS Tracker

Tera Portföy Yönetimi A.Ş.'nin TEFAS'taki fonlarını her sabah (hafta içi,
BIST açılışından ~1 saat önce) kontrol edip Telegram'a bildirim atan bot.

## Ne yapıyor

1. **Günlük** — TEFAS'ın resmi API'sinden her Tera fonunun varlık sınıfı
   dağılımını (Hisse Senedi %, Kamu Borçlanma %, Ters Repo % vb.) çeker,
   bir önceki işlem gününe göre kıyaslar, artan kalemleri bildirir.
2. **KAP pay alım/satım bildirimleri** — Tera Portföy Yönetimi A.Ş.'nin
   KAP'a düştüğü yeni bir "Pay Alım Satım Bildirimi" olduğunda (bir fonu
   bir hissede belirli bir eşiği geçtiğinde dosyalanır), hangi fonun
   hangi hissede işlem bildirdiğini gösterir. Bu, aylık değil olay
   bazlıdır — yeni bildirim geldikçe, genelde haftada birkaç kez düşer.

## Bilinen sınırlama / tasarım kararı

TEFAS **günlük** olarak sadece varlık sınıfı bazında veri yayınlıyor;
hisse bazlı veri hiç yok. İlk tasarımda KAP'ın aylık "Fon Portföy
Dağılım Raporu" yayınladığı varsayılmıştı, ama canlı kontrol (Tera
Portföy Yönetimi'nin 180 günlük / 90 bildirimlik geçmişi) böyle bir
rapor türünün bu fonlar için **hiç dosyalanmadığını** gösterdi. Bunun
yerine gerçek sinyal "Pay Alım Satım Bildirimi" — bir fon bir hissede
eşik aştığında dosyalanan, hem hisseyi hem fonu içeren bildirim.
`disclosureBody` HTML'inden "İlgili Şirketler" / "İlgili Fonlar"
alanlarını regex ile ayrıştırıyoruz; format değişirse ayrıştırma
sessizce boş dönebilir — bu durumda bot çökmez, "yeni bildirim var ama
ayrıştırılamadı" diyip linki verir.

Hem TEFAS hem KAP tarafındaki istekler, bu kodun yazıldığı ortamdan
tefas.gov.tr/kap.org.tr'ye erişim engelli olduğu için doğrudan bu
sandbox'tan test edilemedi — bunun yerine geçici bir "debug probe"
GitHub Actions workflow'u ile gerçek API cevapları defalarca incelenip
kod buna göre düzeltildi (bkz. git geçmişi).

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
