"""Verify mobile layout after nav-in-page fix"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        # iPhone viewport
        ctx = await browser.new_context(
            viewport={"width": 375, "height": 812},
            device_scale_factor=2,
        )
        page = await ctx.new_page()
        await page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        
        # Check measurements
        info = await page.evaluate("""() => {
            const page = document.querySelector('.page');
            const pr = page.getBoundingClientRect();
            const vw = window.innerWidth;
            const nav = document.querySelector('.nav');
            const nr = nav ? nav.getBoundingClientRect() : null;
            
            // Check for any overflow
            const all = document.querySelectorAll('*');
            const wide = [];
            for (const el of all) {
                const r = el.getBoundingClientRect();
                if (r.width > vw + 2 && el.tagName !== 'HTML' && el.tagName !== 'BODY') {
                    wide.push({
                        tag: el.tagName,
                        cls: (el.className || '').slice(0,25),
                        w: Math.round(r.width),
                        vw: vw,
                        l: Math.round(r.left),
                        r: Math.round(r.right)
                    });
                    if (wide.length >= 10) break;
                }
            }
            
            // Check first child (user_bar) left position
            const first = page.firstElementChild;
            const fr = first ? first.getBoundingClientRect() : null;
            
            return {
                vw: vw,
                page: {
                    left: Math.round(pr.left),
                    right: Math.round(pr.right),
                    width: Math.round(pr.width)
                },
                nav: nr ? {left: Math.round(nr.left), width: Math.round(nr.width)} : null,
                firstChild: fr ? {left: Math.round(fr.left), width: Math.round(fr.width)} : null,
                wideElements: wide,
                visibleLeftPad: pr.left,
                visibleRightPad: vw - pr.right
            };
        }""")
        
        for k, v in info.items():
            print(f"{k}: {v}")
        
        # Take screenshot
        await page.screenshot(path="/tmp/iphone_final.png", full_page=False)
        print("\nScreenshot saved to /tmp/iphone_final.png")
        
        await ctx.close()
        await browser.close()

asyncio.run(main())
