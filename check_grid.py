"""Check 960px and 1024px widths (2-column grid zone)"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        for w in [960, 1024, 1100]:
            ctx = await browser.new_context(viewport={"width": w, "height": 800})
            pg = await ctx.new_page()
            await pg.goto("http://127.0.0.1:8080/", wait_until="networkidle")
            await pg.screenshot(path=f"/tmp/compare_{w}.png", full_page=False)
            
            # Check layout
            info = await pg.evaluate("""() => {
                const page = document.querySelector('.page');
                const pr = page.getBoundingClientRect();
                const vw = window.innerWidth;
                const grid = document.querySelector('.jobs-list');
                const gs = grid ? getComputedStyle(grid) : null;
                return {
                    vw: vw,
                    pageLeft: Math.round(pr.left),
                    pageRight: Math.round(pr.right),
                    pageWidth: Math.round(pr.width),
                    leftMargin: Math.round(pr.left),
                    rightMargin: Math.round(vw - pr.right),
                    gridColumns: gs ? gs.gridTemplateColumns : 'n/a',
                    pageMaxWidth: getComputedStyle(page).maxWidth
                };
            }""")
            print(f"\n=== {w}px ===")
            for k, v in info.items():
                print(f"  {k}: {v}")
            
            await ctx.close()
        
        await browser.close()

asyncio.run(main())
