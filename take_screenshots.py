"""Take screenshots at common desktop widths"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        # Take screenshots at common widths - viewport only
        widths = [(1366, 768), (1440, 900), (1920, 1080)]
        
        for w, h in widths:
            ctx = await browser.new_context(viewport={"width": w, "height": h})
            pg = await ctx.new_page()
            await pg.goto("http://127.0.0.1:8080/", wait_until="networkidle")
            await pg.screenshot(path=f"/tmp/compare_{w}.png", full_page=False)
            await ctx.close()
        
        await browser.close()

asyncio.run(main())
print("Screenshots taken")
