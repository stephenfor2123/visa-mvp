import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True)
        page = await ctx.new_page()
        await page.goto("http://127.0.0.1:5173/", wait_until="domcontentloaded", timeout=15000)
        # 强制中文, 跟 prod 一致
        await page.add_init_script("localStorage.setItem('visa.lang', 'zh-CN')")
        await page.reload(wait_until="networkidle", timeout=20000)
        # 等 hero 出现 + 视频开始播放
        await page.wait_for_selector(".hero--slideshow", timeout=10000)
        # 等几秒让视频走到一帧能看清的镜头
        await asyncio.sleep(2.5)
        # 截整个 hero 区域
        await page.locator(".hero--slideshow").screenshot(
            path="/Users/apple/Desktop/签证项目/sources/design-references/_current-home-w29-banner-contrast.png"
        )
        print("OK")
        await browser.close()

asyncio.run(main())
