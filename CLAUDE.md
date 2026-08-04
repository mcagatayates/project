# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repository currently consists of a single file: `x`. There is no `package.json`,
build config, linter config, test framework, or README. `x` has no file extension, but
its contents are a JSX/React source file (it uses JSX syntax, hooks, and ES module
imports) — treat it as if it were `App.jsx`.

Because there is no build tooling in the repo, there are no build/lint/test commands to
run. If you add tooling (e.g. a Vite/CRA scaffold, ESLint, a test runner), document the
resulting commands here.

## What `x` is

`x` is the entire implementation of **FocusBuddy**, a single-page ADHD-focused
productivity companion app: a Pomodoro-style focus timer, a task list ("Missions"),
a points/streak/rank system, ambient focus audio, and a small SEO-oriented blog. The
whole app is one default-exported `App` component plus a few small helper components,
all in this one file.

## Runtime environment assumptions

The file assumes it runs inside a host environment (the pattern of injected globals
`__firebase_config`, `__app_id`, `__initial_auth_token` matches AI-Studio-style
"canvas"/sandbox hosts) that injects three globals before this module executes:

- `__firebase_config` — a JSON string parsed into the Firebase config passed to
  `initializeApp`.
- `__app_id` — used as the top-level Firestore path segment (`artifacts/{appId}/...`);
  falls back to `'focusbuddy-global-v1'` if undefined.
- `__initial_auth_token` — if present, used with `signInWithCustomToken`; otherwise the
  app falls back to `signInAnonymously`.

Any change to how/where this file is run needs to account for these globals being
supplied externally — they are not defined anywhere in this file.

## Architecture (single-file, all in `x`)

The component is organized as a set of `useEffect`-driven "engines" plus tab-switched
views, all sharing one flat `useState` state tree in `App`:

- **Auth flow** — signs the user in (custom token or anonymous) via Firebase Auth,
  then tracks `user` via `onAuthStateChanged`. Nothing else in the app renders its
  real content until `user` is set (see the loading-state early return).
- **Real-time sync** — once `user` exists, three Firestore `onSnapshot` listeners keep
  local state in sync with:
  - `artifacts/{appId}/users/{uid}/tasks` → `tasks`
  - `artifacts/{appId}/users/{uid}/braindump` → `brainDump`
  - `artifacts/{appId}/users/{uid}/stats/overall` → `stats` (`points`, `streak`,
    `sessions`); this doc is auto-created with defaults if it doesn't exist yet.
  All writes (`addDoc`/`updateDoc`/`deleteDoc`/`setDoc`) go straight to these same
  Firestore paths from event handlers — there is no separate data-access layer.
- **Timer engine** — a `setInterval`-based countdown (`timeLeft`, `isActive`) driving
  25-minute focus / 5-minute break cycles. On reaching zero, `completeSession()` awards
  points (30 for a focus session, 5 for a break), toggles `isBreak`, and resets
  `timeLeft`, all persisted via `updateDoc` on the `stats/overall` doc.
  `getRank(points)` derives a display rank (Novice/Focused/Expert/Master) purely from
  `stats.points`; it's not stored separately.
- **Audio engine** — a separate effect owns a single `Audio` instance in `audioRef`,
  swapped whenever `currentMusic` changes (track list in `musicTracks`, streamed from
  external URLs).
- **Views** — `activeTab` (`home` | `focus` | `missions` | `blog` | `settings`)
  selects between `HomeView`, `FocusView`, an inline missions section, `BlogView`, and
  `SettingsView`, all defined inside/near `App` and rendered in `<main>`. `BlogView`
  toggles between a list and a detail view using local `selectedPost` state; blog
  content (`blogPosts`) is static, hardcoded data, not fetched from anywhere.
  Navigation between tabs is a fixed bottom bar built from the small `NavBtn`
  component.
- **`AdSenseUnit`** — a small presentational component rendering a Google AdSense slot
  (`data-ad-client`/`data-ad-slot`); it appears at the bottom of most views with a
  distinct `slot` name per placement.

## Conventions used throughout `x`

- **Styling**: Tailwind utility classes inline on every element; no CSS modules or
  styled-components. Dark mode is a boolean (`darkMode`) persisted to
  `localStorage['fb-dark-mode']` and applied by toggling the `dark` class on
  `document.documentElement`; most classNames pair a light-mode Tailwind class with a
  `dark:` variant conditionally via template literals rather than relying solely on
  Tailwind's `dark:` prefix.
- **Icons**: all icons come from `lucide-react`, imported individually by name.
- **Firestore paths**: always nested under `artifacts/{appId}/users/{uid}/...` — follow
  this convention if adding new synced collections.
- **No separate types/interfaces**: this is plain JS/JSX (not TypeScript); data shapes
  (e.g. a task's `{ text, completed, energy, createdAt }`) are implicit and only
  discoverable by reading the `addDoc`/`updateDoc` call sites.
