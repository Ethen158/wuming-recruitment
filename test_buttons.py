"""Test copy and share buttons work"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        
        context = await browser.new_context(
            viewport={"width": 375, "height": 812},
            device_scale_factor=2,
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = await context.new_page()
        
        # Grant clipboard permission
        await context.grant_permissions(["clipboard-read", "clipboard-write"])
        
        await page.goto("http://127.0.0.1:8080/", wait_until="networkidle")
        
        # Find and click the first 📋 button
        btn = await page.query_selector('.act-btn')
        if btn:
            text = await btn.inner_text()
            print(f"Button text: '{text}'")
            
            # Click it
            await btn.click()
            await asyncio.sleep(0.5)
            
            # Check if button text changed to ✅
            new_text = await btn.inner_text()
            print(f"After click: '{new_text}'")
            
            if '已复制' in new_text:
                print("✅ Copy button works!")
            else:
                print(f"❌ Copy button didn't show '已复制', got: '{new_text}'")
                
            # Try to read clipboard
            try:
                clip = await page.evaluate("navigator.clipboard.readText()")
                print(f"📋 Clipboard: {clip[:80]}...")
            except:
                print("⚠️ Cannot read clipboard via API (expected on HTTP)")
                
                # Alternative: check if JS executed without error
                console_logs = await page.evaluate("""() => {
                    // Check if the copy function was called
                    return window._copyCalled || 'no flag';
                }""")
                print(f"Copy function flag: {console_logs}")
        else:
            print("❌ No copy button found")
        
        # Check for console errors
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await asyncio.sleep(0.5)
        
        if errors:
            print(f"❌ Page errors: {errors}")
        else:
            print("✅ No JavaScript errors")
        
        await browser.close()

asyncio.run(main())
