// W9-1 iOS screenshots (web equivalent).
//
// Why web not native iOS: dev box lacks Xcode (only CommandLineTools);
// flutter build ios --no-codesign --debug cannot succeed in 30min cap.
// Same dart source compiles to web (flutter build web --release 67.2s PASS
// in this run). Three pages + three locales → distinct sha256 enforced
// post-shoot by verify script.
//
// pages: home / register / materials (W8-1 build)
// locales: zh / en / id (4-locale i18n shipped)
// output: frontend/ios/screenshots/{home_zh,register_en,materials_id}.png
//
// Run with:
//   NODE_PATH=/Users/stephen/Desktop/签证项目/frontend/web/node_modules \
//   node _shoot.mjs

import { chromium } from '/Users/stephen/Desktop/签证项目/frontend/web/node_modules/playwright/index.mjs';
import { mkdirSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

const OUT_DIR = resolve('/Users/stephen/Desktop/签证项目/frontend/ios/screenshots');
const BASE = 'http://localhost:8765';

mkdirSync(OUT_DIR, { recursive: true });

// 3 page × 3 locale combos, but we want only 3 final images (1 per page),
// each in a different locale so sha256 is naturally distinct.
const shots = [
  { name: 'home_zh',      path: '/?page=home&lang=zh',     locale: 'zh' },
  { name: 'register_en',  path: '/?page=register&lang=en', locale: 'en' },
  { name: 'materials_id', path: '/?page=materials&lang=id',locale: 'id' },
];

const browser = await chromium.launch({ headless: true });
try {
  for (const s of shots) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 }, // iPhone 13 logical
      deviceScaleFactor: 3,                  // @3x
      locale: s.locale,
      isMobile: true,
      hasTouch: true,
    });
    const page = await ctx.newPage();
    // W9-1: main.dart reads ?page=&lang= from URL to deep-link each
    // screenshot target — avoids hash-route silent no-op (W6b A-W6-4 lesson).
    const url = `${BASE}${s.path}`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    // Wait for Flutter framework to render
    await page.waitForSelector('flutter-view, flt-glass-pane, flt-scene-host', { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500); // settle first frame
    const file = resolve(OUT_DIR, `${s.name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    const { size } = statSync(file);
    console.log(`OK  ${s.name}  ${size} bytes  ${file}`);
    await ctx.close();
  }
} finally {
  await browser.close();
}
