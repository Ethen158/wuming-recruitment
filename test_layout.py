"""Test mobile layout by taking screenshots at multiple widths"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Test iPhone SE width (375px) - very common small phone
        context = await browser.new_context(
            viewport={"width": 375, "height": 812},
            device_scale_factor=2,
        )
        page = await context.new_page()
        await page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        await page.screenshot(path="/tmp/mobile_375.png", full_page=True)
        
        # Measure page container left/right offset
        dims = await page.evaluate("""() => {
            const page = document.querySelector('.page');
            if (!page) return {error: 'no .page'};
            const rect = page.getBoundingClientRect();
            const bodyRect = document.body.getBoundingClientRect();
            const vw = window.innerWidth;
            return {
                pageLeft: rect.left,
                pageRight: rect.right,
                pageWidth: rect.width,
                bodyWidth: bodyRect.width,
                vw: vw,
                leftMargin: rect.left,
                rightMargin: vw - rect.right,
                isCentered: Math.abs(rect.left - (vw - rect.right)) < 2
            };
        }""")
        print(f"iPhone 375px: {json.dumps(dims, indent=2)}")
        
        # Also test on wider mobile
        context2 = await browser.new_context(
            viewport={"width": 414, "height": 896},
            device_scale_factor=2,
        )
        page2 = await context2.new_page()
        await page2.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        await page2.screenshot(path="/tmp/mobile_414.png", full_page=True)
        
        dims2 = await page2.evaluate("""() => {
            const page = document.querySelector('.page');
            if (!page) return {error: 'no .page'};
            const rect = page.getBoundingClientRect();
            const vw = window.innerWidth;
            return {
                pageLeft: rect.left,
                pageRight: rect.right,
                pageWidth: rect.width,
                vw: vw,
                leftMargin: rect.left,
                rightMargin: vw - rect.right,
                isCentered: Math.abs(rect.left - (vw - rect.right)) < 2
            };
        }""")
        print(f"iPhone 414px: {json.dumps(dims2, indent=2)}")
        
        # Check for any elements wider than viewport
        overflow = await page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            const wide = [];
            for (const el of all) {
                const r = el.getBoundingClientRect();
                if (r.width > window.innerWidth + 1 && el.tagName !== 'HTML' && el.tagName !== 'BODY') {
                    wide.push({
                        tag: el.tagName,
                        cls: el.className.slice(0,40),
                        w: r.width,
                        vw: window.innerWidth
                    });
                }
            }
            return wide.slice(0,20);
        }""")
        print(f"Overflow elements: {json.dumps(overflow, indent=2)}")
        
        await browser.close()

import json
asyncio.run(main())
