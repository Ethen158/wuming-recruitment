"""Debug mobile layout by taking actual browser screenshots"""
import asyncio, json, os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        # Test on iPhone SE (375px) - narrow screen
        for name, w, h in [("iPhone_SE", 375, 812), ("iPhone_Plus", 414, 896), ("Galaxy_S20", 360, 800)]:
            context = await browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=2,
            )
            page = await context.new_page()
            await page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
            
            # Save screenshot
            path = f"/tmp/mobile_{name}.png"
            await page.screenshot(path=path, full_page=True)
            
            # Measure page container
            dims = await page.evaluate("""() => {
                const page = document.querySelector('.page');
                if (!page) return {error: 'no .page'};
                const pr = page.getBoundingClientRect();
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                
                // Check body
                const br = document.body.getBoundingClientRect();
                
                // Check nav
                const nav = document.querySelector('.nav');
                const nr = nav ? nav.getBoundingClientRect() : null;
                
                // Find any element wider than viewport
                const all = document.querySelectorAll('*');
                const wide = [];
                for (const el of all) {
                    const r = el.getBoundingClientRect();
                    if (r.width > vw + 1 && el.tagName !== 'HTML' && el.tagName !== 'BODY') {
                        wide.push({
                            tag: el.tagName.slice(0,10),
                            cls: (el.className || '').slice(0,30),
                            w: Math.round(r.width),
                            vw: vw,
                            left: Math.round(r.left),
                            right: Math.round(r.right)
                        });
                        if (wide.length >= 10) break;
                    }
                }
                
                return {
                    viewport: {w: vw, h: vh},
                    body: {w: Math.round(br.width), h: Math.round(br.height), left: Math.round(br.left)},
                    page: {
                        left: Math.round(pr.left),
                        right: Math.round(pr.right),
                        width: Math.round(pr.width),
                        leftPad: Math.round(pr.left),
                        rightPad: Math.round(vw - pr.right),
                        symmetric: Math.abs(pr.left - (vw - pr.right)) < 2
                    },
                    nav: nr ? {
                        left: Math.round(nr.left),
                        width: Math.round(nr.width),
                        right: Math.round(nr.right)
                    } : null,
                    wideElements: wide
                };
            }""")
            
            print(f"\n=== {name} ({w}px) ===")
            print(json.dumps(dims, indent=2))
            
            await context.close()
        
        await browser.close()

asyncio.run(main())
