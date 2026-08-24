# Implementation Plan — Etsy → Logo İşbaşı İstisna Fatura Otomasyonu

## 1. Girdi denetimi (repository taraması sonucu)

Görev tanımının "Repository içinde bulunacak girdiler" bölümünde listelenen dosyalar
kontrol edildi (`find / -iname "*logo*" -o -iname "*etsy*"`, tüm repo ağacı):

| Beklenen girdi | Durum |
|---|---|
| `docs/logo-isbasi-api/` (Logo İşbaşı API dokümanları) | **YOK** |
| `fixtures/etsy-single-item.eml` | **YOK** |
| `fixtures/etsy-multiple-items.eml` | **YOK** |
| `fixtures/etsy-discount-shipping.eml` | **YOK** |
| `docs/accounting-rules.md` | **YOK** |

Repo'da bulunan tek içerik, bu görevle ilgisiz `tera-tefas-tracker/` (Python, TEFAS/KAP
takip botu) klasörüdür.

### Karar (görev talimatına göre)

Talimat açıkça şunu söylüyor: *"Bu dosyalardan biri yoksa Logo endpointi, e-posta formatı,
istisna kodu veya muhasebe kuralı uydurma. Eksik noktayı açık bir blocker olarak kaydet.
Mevcut bilgilerle geliştirilebilen diğer bölümleri tamamla."*

Bu nedenle:

1. **Logo İşbaşı gerçek istemcisi BLOKE.** `docs/logo-isbasi-api/` yok → gerçek endpoint,
   authentication yöntemi, request/response alanları bilinmiyor. `RealLogoIsbasiClient`
   içinde her metot `TODO: BLOCKED_BY_LOGO_API_DOCUMENTATION` ile işaretlenip
   `LogoApiNotConfiguredError` fırlatacak. Endpoint/payload **uydurulmayacak**.
   Buna karşın `LogoClient` arayüzü, `MockLogoClient` (testler ve `LOGO_BASE_URL`
   tanımsızken varsayılan olarak kullanılan sahte istemci) ve mock HTTP sunucusu
   eksiksiz üretilecek — bu kısımlar Logo'nun *gerçek* sözleşmesine değil, sistemin
   kendi domain arayüzüne (draft oluştur / sorgula / finalize et) bağlı olduğundan
   uydurma kapsamına girmiyor.
2. **Muhasebe politikası BLOKE.** `docs/accounting-rules.md` yok → Etsy'nin tahsil ettiği
   satış vergisi/VAT, kargo, indirim ve platform ücretinin faturaya nasıl yansıyacağı
   (ayrı kalem mi, brüt/net mi, istisna kapsamına dahil mi) mali müşavir onayı
   gerektiren bir karardır ve **verilmeyecek**. `invoice-policy` modülü bu kuralları
   `docs/accounting-rules.md` dosyasından okuyacak şekilde tasarlanacak; dosya yoksa
   politika `UNRESOLVED` kabul edilir ve `order-validator` bunu zorunlu bir doğrulama
   hatası olarak işler (`ACCOUNTING_POLICY_NOT_DEFINED`) → sipariş `MANUAL_REVIEW`'a
   düşer, **hiçbir taslak fatura oluşturulmaz**. Dosyanın beklenen alan/şema örneği
   `docs/accounting-rules.example.md` olarak (doldurulacak şablon, onaylı kural değil)
   eklenecek.
3. **E-posta fixture'ları ÜRETİLECEK (sentetik).** Görev tanımının "Teslimatlar"
   bölümü ayrıca "Örnek anonim e-posta fixture'ları" üretilmesini istiyor. Bu nedenle
   `tests/fixtures/*.eml` altında, gerçek bir Etsy siparişine dayanmayan, tamamen
   kurgusal/anonim alıcı bilgileriyle **sentetik** test e-postaları oluşturulacak.
   Bunlar Etsy'nin *gerçek* güncel e-posta şablonunun birebir kopyası olduğu iddiasında
   değildir — parser'ı test etmek için temsili bir yapı sağlar. Bu durum
   `IMPLEMENTATION_STATUS.md` içinde açık bir uyarı olarak not edilecek: format,
   gerçek üretim trafiğinden gelen örneklerle doğrulanmadan production'a alınmamalı.
   Parser, tanımadığı bir yapı gördüğünde veri **uydurmaz**, siparişi `MANUAL_REVIEW`
   durumuna düşürür (bu davranış birim testleriyle kanıtlanacak).
4. Etsy Open API v3 (receipts/transactions), Gmail API OAuth2, Fastify, Prisma,
   PostgreSQL, Zod, Vitest, Docker gibi teknolojiler kamuya açık ve stabil şekilde
   belgeli oldukları için (ve görev bunları açıkça istediği için) gerçek entegrasyon
   kodu yazılacaktır — bunlar "Logo endpoint/format" uydurma yasağının kapsamında
   değildir.

## 2. Modül planı

- `mail-provider`: `MailProvider` arayüzü + `GmailMailProvider` (googleapis, OAuth2,
  `ETSY_MAIL_QUERY` ile arama, label ekleme sadece fatura başarılı olunca).
- `etsy-email-parser`: deterministik, regex/DOM tabanlı (LLM YOK) parser. HTML ve
  plain-text günlük çözümleyiciler. Alan çıkaramazsa/eminliği düşükse `MANUAL_REVIEW`.
- `etsy-api`: Etsy Open API v3 `getShopReceipt` / `getShopReceiptTransactionsByReceipt`
  istemcisi; env değişkenleri tanımlıysa aktif, e-posta verisiyle çapraz doğrulama.
- `order-validator`: Zod şemaları + iş kuralları (toplam tutar toleransı, zorunlu
  alanlar, muhasebe politikası varlığı, mükerrer sipariş kontrolü).
- `invoice-policy`: `docs/accounting-rules.md` yükleyici + istisna kodu/KDV/senaryo
  env değişkenlerinden okunan politika nesnesi üretimi.
- `logo-isbasi-client`: `LogoClient` arayüzü, `RealLogoIsbasiClient` (bloke stub),
  `MockLogoClient` (test/varsayılan sahte istemci, taslak oluşturma, sorgulama,
  finalize, hata simülasyonu).
- `invoice-service`: orkestrasyon — validate → dedup kontrolü → idempotency sorgusu →
  draft oluştur → kaydet → (opsiyonel) finalize.
- `job-worker`: periyodik Gmail taraması + kuyruk işleme, retry/backoff.
- `audit-log`: PII redakte edilmiş audit kaydı.
- `admin-panel`: Fastify + basic-auth korumalı, sunucu taraflı render edilen HTML panel.

## 3. Sıra

1. ✅ Girdi taraması (bu doküman).
2. Proje iskeleti (package.json, tsconfig, prisma schema).
3. Çekirdek modüllerin implementasyonu.
4. Mock Logo sunucusu + sentetik `.eml` fixture'ları.
5. Testler (Vitest) — 15 senaryo.
6. `prisma migrate` ile migration üretimi + yerel Postgres üzerinde doğrulama.
7. `vitest run`, `tsc --noEmit`, `eslint` çalıştırma, hataların giderilmesi.
8. `docker build` doğrulaması.
9. `IMPLEMENTATION_STATUS.md` ile sonuçların ve gerçek blocker'ların raporlanması.
