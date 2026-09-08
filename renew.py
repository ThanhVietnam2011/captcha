import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        # Khởi tạo trình duyệt
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Đăng nhập vào Zampto
        await page.goto("https://dash.zampto.net/login")
        await page.fill('input[name="email"]', "YOUR_EMAIL")
        await page.fill('input[name="password"]', "YOUR_PASSWORD")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(5000)

        # 2. Truy cập trang quản lý Server
        await page.goto("https://dash.zampto.net/server/YOUR_SERVER_ID")
        
        # 3. Đợi Cloudflare Turnstile tự động load và verify xong
        await page.wait_for_timeout(8000) 

        # 4. Tìm và click nút Renew Server (dựa vào text trên nút)
        renew_button = page.get_by_role("button", name="Renew Server")
        if await renew_button.is_visible():
            await renew_button.click()
            print("Đã bấm Renew thành công!")
        
        await browser.close()

asyncio.run(run())
