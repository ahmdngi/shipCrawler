# Mobile Compatability + PWA + Collapsed Panels Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make Shipcrawler dashboard installable as a PWA, responsive on mobile/tablet, and start with both side panels collapsed by default.

**Architecture:** Pure frontend changes (HTML, CSS, JS) plus two static files (manifest.json, service-worker.js). No Flask backend changes needed — Flask's static file serving already handles `/static/` paths.

**Tech Stack:** Vanilla HTML/CSS/JS, Flask static serving, Web App Manifest, Service Worker API.

---

## Task 1: Panels collapsed by default

**Objective:** Both sidebar (left) and right panel start closed on every fresh load. User expands them via toggle buttons.

**Files:**
- Modify: `/root/shipcrawler/static/js/shipcrawler-core.js` (~line 58-61)

**Details:**

Change the init logic so panels default to closed instead of open:

```js
// Current (line 58-60):
var sidebarOpen = localStorage.getItem('shipcrawler-sidebar-open') !== 'false';

// New — default closed, respect saved preference only if previously explicitly opened
var sidebarOpen = localStorage.getItem('shipcrawler-sidebar-open') === 'true';
```

Also add right-panel default-closed logic after the sidebar init:

```js
var rightPanelOpen = localStorage.getItem('shipcrawler-rightpanel-open') === 'true';
if (!rightPanelOpen) {
  document.getElementById('right-panel').classList.add('closed');
  document.body.classList.add('right-panel-closed');
}
```

Fix the right-panel toggle to persist state (currently missing localStorage save):

```js
function toggleRightPanel() {
  var rp = document.getElementById('right-panel');
  var isClosed = rp.classList.toggle('closed');
  document.body.classList.toggle('right-panel-closed', isClosed);
  localStorage.setItem('shipcrawler-rightpanel-open', String(!isClosed));
  document.getElementById('right-panel-toggle').textContent = isClosed ? '▶' : '◀';
}
```

**Verification:** Reload page — both panels are collapsed showing only toggle buttons. Open and close each — state persists across reload.

---

## Task 2: PWA — manifest.json

**Objective:** Add a Web App Manifest so the dashboard can be installed as a PWA on mobile/desktop.

**Files:**
- Create: `/root/shipcrawler/static/manifest.json`

**manifest.json:**

```json
{
  "name": "Shipcrawler OSINT Dashboard",
  "short_name": "Shipcrawler",
  "description": "AI-powered maritime OSINT investigation platform",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0e17",
  "theme_color": "#0a0e17",
  "orientation": "any",
  "icons": [
    {
      "src": "/static/favicon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/static/favicon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

Also generate two PNG favicons from the existing SVG:
- `static/favicon-192.png` — 192×192 green globe
- `static/favicon-512.png` — 512×512 green globe

Since we can't easily generate PNGs, use an inline SVG approach or generate with Python Pillow.

**Verification:** `curl http://localhost:9091/static/manifest.json` returns valid JSON.

---

## Task 3: PWA — Service Worker

**Objective:** Register a service worker that caches essential assets for offline use and enables PWA install prompt.

**Files:**
- Create: `/root/shipcrawler/static/sw.js`
- Modify: `/root/shipcrawler/templates/index.html` (register SW)

**sw.js — cache-first for static assets, network-first for API:**

```js
const CACHE = 'shipcrawler-v1';
const ASSETS = [
  '/',
  '/static/css/shipcrawler.css',
  '/static/js/shipcrawler-core.js',
  '/static/js/shipcrawler-ui.js',
  '/static/js/shipcrawler-sse.js',
  '/static/js/globe.js',
  '/static/manifest.json',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(cache => cache.addAll(ASSETS))
  );
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(cached => cached || fetch(e.request))
  );
});
```

**In index.html head**, add before closing `</head>`:

```html
<link rel="manifest" href="/static/manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Shipcrawler">
<script>if('serviceWorker' in navigator) navigator.serviceWorker.register('/static/sw.js');</script>
```

**Verification:** Open DevTools > Application > Service Workers — shows registered and activated. Lighthouse PWA audit passes basic checks.

---

## Task 4: Mobile responsive CSS

**Objective:** All layouts adapt to tablet (<1024px) and phone (<768px) screens. Panels behave as overlays on mobile.

**Files:**
- Modify: `/root/shipcrawler/static/css/shipcrawler.css`

**Media queries to add (at end of file):**

```css
/* ─── Tablet: <1024px ───────────────────────── */
@media (max-width: 1024px) {
  body { margin-left: 0; margin-right: 0; }
  body.sidebar-closed,
  body.right-panel-closed { margin: 0; }

  .sidebar {
    width: 280px;
    transform: translateX(-100%);
    z-index: 200;
  }
  .sidebar.open { transform: translateX(0); }
  .sidebar.closed { transform: translateX(-100%); }
  .sidebar.closed .sidebar-toggle { display: none; }

  .right-panel {
    width: 280px;
    transform: translateX(100%);
    z-index: 200;
  }
  .right-panel.open { transform: translateX(0); }
  .right-panel.closed { transform: translateX(100%); }
  .right-panel.closed .right-panel-toggle { display: none; }

  .sidebar-overlay {
    display: none;
    position: fixed; inset: 0; z-index: 199;
    background: rgba(0,0,0,0.5);
  }
  .sidebar-overlay.active { display: block; }

  .hero h1 { font-size: 2rem; }
  .hero p { font-size: 0.9rem; }
  .card-wrapper { grid-template-columns: 1fr; }
  .report-header { flex-direction: column; gap: 0.5rem; }
  .nav-links { gap: 0.5rem; }
}

/* ─── Phone: <768px ─────────────────────────── */
@media (max-width: 768px) {
  .hero { padding: 3rem 1rem; }
  .hero h1 { font-size: 1.6rem; }
  .hero p { font-size: 0.82rem; }
  .hero-badge { font-size: 0.7rem; }

  .search-container form { flex-direction: column; }
  #search-input { min-width: unset; width: 100%; }
  #search-btn { width: 100%; }

  .terminal-window { margin: 1rem; }
  .terminal-titlebar { padding: 0.3rem 0.6rem; }
  .terminal-title { font-size: 0.7rem; }

  .tab-bar { overflow-x: auto; gap: 0.3rem; }
  .tab-btn { font-size: 0.75rem; padding: 0.4rem 0.7rem; white-space: nowrap; }

  .card { padding: 0.8rem; }
  .card-grid { grid-template-columns: 1fr; }

  .final-summary { flex-direction: column; gap: 0.5rem; padding: 0.8rem; margin: 0 1rem; }
  .summary-stat { flex-direction: row; justify-content: space-between; }

  .report-section { padding: 0 0.5rem; }
  .report-actions { flex-wrap: wrap; }

  nav { padding: 0.6rem 1rem; }
  .brand { font-size: 0.9rem; }
  .nav-links { gap: 0.3rem; }
  .theme-pill { font-size: 0.7rem; padding: 0.2rem 0.5rem; }

  .mode-toggle { gap: 0.3rem; }
  .mode-btn { font-size: 0.78rem; padding: 0.4rem 0.8rem; }
}
```

**Key mobile behaviour:**
- Body has no margin (full width)
- Sidebar slides in from left as overlay with dark backdrop
- Right panel slides in from right as overlay
- Toggle buttons hidden when panel is closed on mobile (use floating FAB-like buttons or nav icons instead)
- All grids collapse to single column
- Terminal and hero scale down

---

## Task 5: Mobile toggle buttons (FAB)

**Objective:** On mobile, collapsed panels need discovery buttons since the toggle peeks from the edge. Add floating action buttons.

**Files:**
- Modify: `/root/shipcrawler/templates/index.html` (add FABs after nav)
- Modify: `/root/shipcrawler/static/css/shipcrawler.css` (FAB styles)
- Modify: `/root/shipcrawler/static/js/shipcrawler-core.js` (update toggle for mobile)

**Approach:** Two small floating buttons at bottom-left and bottom-right on mobile only:

```html
<!-- Mobile FABs (hidden on desktop via CSS) -->
<button class="fab fab-left" id="fab-sidebar" onclick="ShipcrawlerCore.toggleSidebar()">☰</button>
<button class="fab fab-right" id="fab-right-panel" onclick="ShipcrawlerCore.toggleRightPanel()">📄</button>
```

**CSS for FABs:**
```css
.fab {
  display: none; /* hidden by default */
  position: fixed; bottom: 1.5rem; z-index: 180;
  width: 44px; height: 44px;
  border-radius: 50%;
  background: var(--color-accent);
  color: var(--color-accent-ink);
  border: none;
  font-size: 1.2rem;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.fab-left { left: 1rem; }
.fab-right { right: 1rem; }
@media (max-width: 768px) {
  .fab { display: flex; align-items: center; justify-content: center; }
}
```

Update `toggleSidebar` and `toggleRightPanel` to handle `.open` class for mobile sliding overlay (instead of the desktop translateX-based `.closed` approach).

---

## Task 6: Testing & Verification

**Objective:** Verify all three features work end-to-end.

**Verification steps:**
1. Fresh page load — both panels collapsed, main content full width
2. Click toggle — panel slides open, content shifts on desktop; overlay appears on mobile
3. Reload — state persists from localStorage
4. Resize to 768px width — everything stacks, FABs appear, panels overlay
5. Open DevTools > Application > Manifest — valid manifest
6. Open DevTools > Application > Service Workers — registered and active
7. Chrome on Android (or emulator) — "Add to Home Screen" prompt appears
8. Run Lighthouse PWA audit

---

## Risks & Tradeoffs

- **PWA icons**: Need to generate PNGs from the SVG globe. Use Python Pillow's `ImageDraw` or embed an SVG data URI as favicon. If PNG generation is complex, skip custom icons and use the existing SVG favicon with a `data:` URI fallback.
- **Mobile panel interaction**: Desktop uses `translateX` with `.closed` class; mobile uses `.open` class with full overlay. The toggle functions need to handle both modes gracefully — check viewport width before applying classes.
- **Service Worker scope**: Flask serves on port 9091, SW scope is `/` — no issues.

---

## Summary of Files Changed

| File | Action |
|------|--------|
| `static/js/shipcrawler-core.js` | Modify — default panels closed, right-panel localStorage, mobile-aware toggle |
| `static/manifest.json` | Create — PWA manifest |
| `static/favicon-192.png` | Create — 192×192 icon |
| `static/favicon-512.png` | Create — 512×512 icon |
| `static/sw.js` | Create — service worker |
| `templates/index.html` | Modify — manifest link, SW registration, FAB buttons, apple meta tags |
| `static/css/shipcrawler.css` | Modify — responsive media queries, FAB styles |
| `README.md` | Modify — changelog entry |
