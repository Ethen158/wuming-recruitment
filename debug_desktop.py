"""Test desktop layout centering"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        # Test desktop at 1280px and 1920px
        for w, h in [(1280, 800), (1440, 900), (1920, 1080)]:
            context = await browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=1,
            )
            page = await context.new_page()
            await page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
            
            dims = await page.evaluate("""() => {
                const page = document.querySelector('.page');
                if (!page) return {error: 'no .page'};
                const pr = page.getBoundingClientRect();
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                
                // Check card heights in same row
                const cards = document.querySelectorAll('.job-card');
                const cardRects = [];
                cards.forEach((c, i) => {
                    const r = c.getBoundingClientRect();
                    cardRects.push({i, top: r.top, h: r.height, left: r.left});
                });
                
                return {
                    viewport: {w: vw, h: vh},
                    page: {
                        left: Math.round(pr.left),
                        right: Math.round(pr.right),
                        width: Math.round(pr.width),
                        leftMargin: Math.round(pr.left),
                        rightMargin: Math.round(vw - pr.right),
                        symmetric: Math.abs(pr.left - (vw - pr.right)) < 2
                    },
                    cards: cardRects.slice(0, 6),
                    availableWidth: Math.round(pr.width) - 40,  // page padding
                };
            }""")
            
            # Take screenshot for visual check
            await page.screenshot(path=f"/tmp/desktop_{w}.png", full_page=False)
            
            print(f"\n=== Desktop {w}x{h} ===")
            print(f"Page: left={dims['page']['left']}px, right={dims['page']['right']}px")
            print(f"Viewport: {dims['viewport']}")
            print(f"Left margin: {dims['page']['leftMargin']}px, Right margin: {dims['page']['rightMargin']}px")
            print(f"Symmetric: {dims['page']['symmetric']}")
            if dims.get('cards'):
                print("Card heights:")
                for c in dims['cards'][:4]:
                    print(f"  Card {c['i']}: top={c['top']}px height={c['h']}px")
                # Check if cards in same row have same height
                if len(dims['cards']) >= 2:
                    same_row = abs(dims['cards'][0]['top'] - dims['cards'][1]['top']) < 5
                    print(f"Cards 0&1 same row: {same_row}")
                    if same_row:
                        h_diff = abs(dims['cards'][0]['h'] - dims['cards'][1]['h'])
                        print(f"Height diff in row: {h_diff}px {'✓' if h_diff < 5 else '✗'}")
            
            await context.close()
        
        await browser.close()

asyncio.run(main())
