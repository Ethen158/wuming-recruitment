"""Take viewport-only screenshots (not full-page) for analysis"""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        # iPhone SE - viewport only
        context = await browser.new_context(
            viewport={"width": 375, "height": 812},
            device_scale_factor=2,
        )
        page = await context.new_page()
        await page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        await page.screenshot(path="/tmp/mobile_viewport.png", full_page=False)
        
        # Also measure the actual content padding by examining first visible element
        padding_info = await page.evaluate("""() => {
            const page = document.querySelector('.page');
            const style = getComputedStyle(page);
            const firstChild = page.firstElementChild;
            const fcStyle = firstChild ? getComputedStyle(firstChild) : null;
            return {
                pagePadding: style.padding,
                pagePaddingLeft: style.paddingLeft,
                pagePaddingRight: style.paddingRight,
                pageBoxSizing: style.boxSizing,
                firstChildTag: firstChild ? firstChild.tagName : 'none',
                firstChildStyle: fcStyle ? {
                    width: fcStyle.width,
                    margin: fcStyle.margin,
                } : null
            };
        }""")
        print(f"Padding info: {json.dumps(padding_info, indent=2)}")
        
        await context.close()
        await browser.close()

asyncio.run(main())
