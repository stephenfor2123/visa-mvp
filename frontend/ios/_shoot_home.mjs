// W33 home-only shoot: capture just the home page so we can iterate the
// country-tile layout fast (the full 3-page shoot still runs in W9-1).
//
// Why this exists: the W9-1 shoot captures 3 pages in 3 different locales,
// and re-running all 3 for a small home-page tweak wastes ~30s and burns
// through Playwright contexts. For W33 (2-col country tile redesign) we
// only need the home page in zh-CN.
//
// Run with:
//   NODE_PATH=/Users/apple/Desktop/签证项目/frontend/web/node_modules \
//   node _shoot_home.mjs

import { chromium } from '/Users/apple/Desktop/签证项目/frontend/web/node_modules/playwright/index.mjs';
import { mkdirSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

const OUT_DIR = resolve('/Users/apple/Desktop/签证项目/frontend/ios/screenshots');
const BASE = 'http://localhost:8765';

mkdirSync(OUT_DIR, { recursive: true });

const shots = [
  { name: 'home_zh', path: '/?page=home&lang=zh', locale: 'zh' },
];

const browser = await chromium.launch({ headless: true });
try {
  for (const s of shots) {
    const ctx = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 3,
      locale: s.locale,
      isMobile: true,
      hasTouch: true,
    });
    const page = await ctx.newPage();
    const url = `${BASE}${s.path}`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForSelector('flutter-view, flt-glass-pane, flt-scene-host', { timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(2500);
    const file = resolve(OUT_DIR, `${s.name}.png`);
    await page.screenshot({ path: file, fullPage: false });
    const { size } = statSync(file);
    console.log(`OK  ${s.name}  ${size} bytes  ${file}`);
    await ctx.close();
  }
} finally {
  await browser.close();
}
