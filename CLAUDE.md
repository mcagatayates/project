# CLAUDE.md

Bu dosya, Claude Code'a (claude.ai/code) bu depoda kod üzerinde çalışırken rehberlik eder.

## Deponun mevcut durumu

Bu depo şu anda tek bir dosyadan oluşuyor: `x`. `package.json`, build (derleme)
yapılandırması, linter yapılandırması, test framework'ü veya README bulunmuyor. `x`
dosyasının bir uzantısı yok, ancak içeriği bir JSX/React kaynak dosyası (JSX sözdizimi,
hook'lar ve ES module import'ları kullanıyor) — dosyayı sanki `App.jsx` imiş gibi ele alın.

Depoda herhangi bir build aracı bulunmadığından çalıştırılacak build/lint/test komutu
yoktur. Eğer bir araç seti eklerseniz (ör. Vite/CRA iskeleti, ESLint, bir test runner),
ortaya çıkan komutları buraya belgeleyin.

## `x` dosyası nedir

`x`, **FocusBuddy** adlı tek sayfalık, DEHB (ADHD) odaklı bir üretkenlik yardımcısı
uygulamasının tüm implementasyonudur: Pomodoro tarzı bir odaklanma zamanlayıcısı, bir
görev listesi ("Missions"), bir puan/seri/rütbe sistemi, ortam odaklanma müziği ve küçük
bir SEO odaklı blog. Uygulamanın tamamı, varsayılan olarak export edilen tek bir `App`
bileşeni ile birkaç küçük yardımcı bileşenden oluşur ve hepsi bu tek dosyada yer alır.

## Çalışma zamanı ortamı varsayımları

Dosya, kendisini çalıştıran bir host ortamı olduğunu varsayar (enjekte edilen
`__firebase_config`, `__app_id`, `__initial_auth_token` global değişkenlerinin deseni,
AI-Studio tarzı "canvas"/sandbox host'larıyla eşleşir) ve bu ortam, modül çalışmadan önce
üç global değişkeni enjekte eder:

- `__firebase_config` — `initializeApp`'e verilen Firebase yapılandırmasına parse edilen
  bir JSON string'i.
- `__app_id` — üst seviye Firestore path segmenti olarak kullanılır
  (`artifacts/{appId}/...`); tanımsızsa `'focusbuddy-global-v1'` değerine düşer (fallback).
- `__initial_auth_token` — mevcutsa `signInWithCustomToken` ile kullanılır; aksi halde
  uygulama `signInAnonymously`'e düşer.

Bu dosyanın nasıl/nerede çalıştırıldığına dair herhangi bir değişiklik, bu global
değişkenlerin dışarıdan sağlandığını göz önünde bulundurmalıdır — bunlar bu dosyanın
hiçbir yerinde tanımlanmamıştır.

## Mimari (tek dosya, tamamı `x` içinde)

Bileşen, `App` içinde tek bir düz `useState` state ağacını paylaşan, `useEffect` ile
yönetilen bir dizi "motor" ile sekme (tab) bazlı view'lardan oluşacak şekilde
organize edilmiştir:

- **Auth akışı** — Firebase Auth üzerinden kullanıcı girişini yapar (custom token veya
  anonim), ardından `onAuthStateChanged` ile `user`'ı takip eder. `user` set edilene
  kadar uygulamanın geri kalanı gerçek içeriğini render etmez (loading-state erken
  return'üne bakın).
- **Gerçek zamanlı senkronizasyon** — `user` mevcut olduğunda, üç Firestore
  `onSnapshot` listener'ı local state'i şunlarla senkronize tutar:
  - `artifacts/{appId}/users/{uid}/tasks` → `tasks`
  - `artifacts/{appId}/users/{uid}/braindump` → `brainDump`
  - `artifacts/{appId}/users/{uid}/stats/overall` → `stats` (`points`, `streak`,
    `sessions`); bu doküman henüz yoksa varsayılan değerlerle otomatik oluşturulur.
  Tüm yazma işlemleri (`addDoc`/`updateDoc`/`deleteDoc`/`setDoc`) event handler'lardan
  doğrudan bu aynı Firestore path'lerine gider — ayrı bir data-access katmanı yoktur.
- **Zamanlayıcı motoru** — 25 dakikalık odaklanma / 5 dakikalık mola döngülerini
  yürüten, `setInterval` tabanlı bir geri sayım (`timeLeft`, `isActive`). Süre sıfıra
  ulaştığında `completeSession()` puan verir (odaklanma seansı için 30, mola için 5),
  `isBreak`'i toggle'lar ve `timeLeft`'i sıfırlar; bunların hepsi `stats/overall`
  dokümanı üzerinde `updateDoc` ile kalıcı hale getirilir. `getRank(points)`, gösterilecek
  rütbeyi (Novice/Focused/Expert/Master) yalnızca `stats.points`'ten türetir; ayrıca
  saklanmaz.
- **Ses motoru** — ayrı bir effect, `audioRef` içinde tek bir `Audio` instance'ı tutar;
  `currentMusic` her değiştiğinde bu instance değiştirilir (parça listesi
  `musicTracks` içinde, harici URL'lerden stream edilir).
- **View'lar** — `activeTab` (`home` | `focus` | `missions` | `blog` | `settings`),
  `HomeView`, `FocusView`, satır içi bir missions bölümü, `BlogView` ve `SettingsView`
  arasında seçim yapar; hepsi `App` içinde/yakınında tanımlıdır ve `<main>` içinde
  render edilir. `BlogView`, local `selectedPost` state'ini kullanarak bir liste ile
  detay görünümü arasında geçiş yapar; blog içeriği (`blogPosts`) statik, hardcoded
  veridir, hiçbir yerden fetch edilmez. Sekmeler arası navigasyon, küçük `NavBtn`
  bileşeninden oluşturulan sabit (fixed) bir alt bardır.
- **`AdSenseUnit`** — bir Google AdSense slotu render eden küçük bir sunum (presentational)
  bileşeni (`data-ad-client`/`data-ad-slot`); çoğu view'ın altında, her yerleşim için
  farklı bir `slot` adıyla görünür.

## `x` genelinde kullanılan kurallar (conventions)

- **Styling**: her elementte satır içi Tailwind utility class'ları; CSS modülleri veya
  styled-components yok. Dark mode, `localStorage['fb-dark-mode']`'da kalıcı hale
  getirilen bir boolean (`darkMode`) olup `document.documentElement` üzerinde `dark`
  class'ının toggle edilmesiyle uygulanır; çoğu className, yalnızca Tailwind'in
  `dark:` prefix'ine güvenmek yerine, light-mode Tailwind class'ını template literal'lar
  aracılığıyla koşullu bir `dark:` varyantıyla eşleştirir.
- **İkonlar**: tüm ikonlar `lucide-react`'ten, isimle tek tek import edilerek gelir.
- **Firestore path'leri**: her zaman `artifacts/{appId}/users/{uid}/...` altında
  iç içe geçmiştir — yeni senkronize edilen collection'lar eklerken bu kurala uyun.
- **Ayrı type/interface yok**: bu düz JS/JSX'tir (TypeScript değil); veri şekilleri
  (ör. bir task'ın `{ text, completed, energy, createdAt }` şekli) örtüktür ve yalnızca
  `addDoc`/`updateDoc` çağrı noktaları okunarak keşfedilebilir.
