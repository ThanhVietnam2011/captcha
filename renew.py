import os
import time
import requests
from playwright.sync_api import sync_playwright

TWOCAPTCHA_API_KEY = os.environ.get("TWOCAPTCHA_API_KEY")
ZAMPTO_EMAIL = os.environ.get("ZAMPTO_EMAIL")
ZAMPTO_PASSWORD = os.environ.get("ZAMPTO_PASSWORD")

def solve_turnstile(sitekey, page_url):
    print("[+] Đang gửi yêu cầu giải Cloudflare Turnstile tới 2Captcha...")
    req_url = f"https://2captcha.com/in.php?key={TWOCAPTCHA_API_KEY}&method=turnstile&sitekey={sitekey}&pageurl={page_url}&json=1"
    res = requests.get(req_url).json()
    
    if res.get("status") != 1:
        raise Exception(f"Lỗi gửi 2Captcha: {res.get('request')}")
    
    request_id = res["request"]
    print(f"[+] ID Captcha: {request_id}. Đang chờ 2Captcha xử lý...")
    
    for _ in range(24):
        time.sleep(5)
        chk_url = f"https://2captcha.com/res.php?key={TWOCAPTCHA_API_KEY}&action=get&id={request_id}&json=1"
        chk_res = requests.get(chk_url).json()
        if chk_res.get("status") == 1:
            print("[+] Giải Captcha thành công!")
            return chk_res["request"]
            
    raise Exception("Hết thời gian chờ giải Captcha từ 2Captcha.")

def main():
    if not TWOCAPTCHA_API_KEY or not ZAMPTO_EMAIL or not ZAMPTO_PASSWORD:
        raise ValueError("Thiếu biến môi trường TWOCAPTCHA_API_KEY, ZAMPTO_EMAIL hoặc ZAMPTO_PASSWORD!")

    os.makedirs("screenshots", exist_ok=True)

    with sync_playwright() as p:
        # Giả lập Chrome thật để tránh bị Cloudflare chặn trên GitHub Actions
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        # BƯỚC 1: Vào trang chủ https://zampto.net/
        print("[1] Đang truy cập trang chủ: https://zampto.net/")
        page.goto("https://zampto.net/", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        print(f"    -> URL hiện tại: {page.url}")
        page.screenshot(path="screenshots/1_home_page.png")

        # BƯỚC 2: Tìm nút Login và ép Playwright điều hướng sang trang Đăng nhập
        print("[2] Đang tìm liên kết 'Login' trên trang chủ...")
        login_href = None
        try:
            login_elem = page.locator('a[href*="login"], a[href*="dash"], a:has-text("Login"), button:has-text("Login")').first
            login_href = login_elem.get_attribute("href")
        except Exception:
            pass

        if login_href:
            if not login_href.startswith("http"):
                login_href = "https://zampto.net" + login_href
            print(f"    -> Lấy được link Login: {login_href}. Đang chuyển trang...")
            page.goto(login_href, wait_until="domcontentloaded")
        else:
            print("    -> Không lấy được href, chuyển thẳng tới https://dash.zampto.net/")
            page.goto("https://dash.zampto.net/", wait_until="domcontentloaded")

        page.wait_for_timeout(4000)
        print(f"    -> URL hiện tại (Trang Login): {page.url}")
        page.screenshot(path="screenshots/2_login_page.png")

        # BƯỚC 3: Điền Email và Password
        print("[3] Đang điền Email và Password...")
        email_selector = 'input[type="email"], input[name="email"], input[placeholder*="email" i]'
        pass_selector = 'input[type="password"], input[name="password"]'
        
        try:
            page.wait_for_selector(email_selector, timeout=20000)
        except Exception:
            page.screenshot(path="screenshots/error_login_form_not_found.png")
            raise Exception(f"Không tìm thấy ô nhập Email tại URL: {page.url}. Hãy kiểm tra ảnh screenshots/2_login_page.png!")

        page.fill(email_selector, ZAMPTO_EMAIL)
        page.fill(pass_selector, ZAMPTO_PASSWORD)

        # BƯỚC 4: Nhấn nút Login để vào Dashboard
        print("[4] Đang nhấn nút 'Login'...")
        submit_btn = page.locator('button[type="submit"], button:has-text("Login"), input[type="submit"]').first
        submit_btn.click()

        page.wait_for_timeout(5000)
        print(f"    -> URL hiện tại (Sau Login): {page.url}")
        page.screenshot(path="screenshots/3_after_login.png")

        # BƯỚC 5: Tìm và bấm nút "View Server"
        print("[5] Đang tìm và nhấn nút 'View Server'...")
        view_server_btn = page.locator('a:has-text("View Server"), button:has-text("View Server"), a[href*="server"]').first
        
        server_href = None
        try:
            server_href = view_server_btn.get_attribute("href")
        except Exception:
            pass

        if server_href:
            if not server_href.startswith("http"):
                server_href = "https://dash.zampto.net" + server_href
            print(f"    -> Chuyển hướng tới chi tiết Server: {server_href}")
            page.goto(server_href, wait_until="domcontentloaded")
        else:
            view_server_btn.click()

        page.wait_for_timeout(4000)
        print(f"    -> URL hiện tại (Trang Chi tiết Server): {page.url}")
        page.screenshot(path="screenshots/4_server_details.png")

        # BƯỚC 6: Quét Turnstile Sitekey & Giải Captcha bằng 2Captcha
        print("[6] Đang quét lấy Cloudflare Turnstile Sitekey...")
        try:
            turnstile_elem = page.wait_for_selector("[data-sitekey]", timeout=15000)
            sitekey = turnstile_elem.get_attribute("data-sitekey")
        except Exception:
            sitekey = page.evaluate('''() => {
                const el = document.querySelector('[data-sitekey]');
                if (el) return el.getAttribute('data-sitekey');
                const iframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
                if (iframe) {
                    const match = iframe.src.match(/sitekey=([^&]+)/);
                    if (match) return match[1];
                }
                return null;
            }''')

        if not sitekey:
            page.screenshot(path="screenshots/error_no_sitekey.png")
            raise ValueError(f"Không tìm thấy Turnstile Sitekey tại URL: {page.url}!")

        print(f"    -> Tìm thấy Turnstile Sitekey: {sitekey}")
        token = solve_turnstile(sitekey, page.url)

        # Chèn Token giải được vào Cloudflare input
        page.evaluate(f'''
            const el = document.querySelector('[name="cf-turnstile-response"]');
            if (el) el.value = "{token}";
        ''')

        # BƯỚC 7: Nhấn Renew Server
        print("[7] Đang nhấn nút Renew Server...")
        renew_button = page.locator("button:has-text('Renew Server')").first
        renew_button.click()

        page.wait_for_timeout(5000)
        print(f"    -> URL hiện tại (Hoàn tất): {page.url}")
        page.screenshot(path="screenshots/5_renew_completed.png")
        print("[+] Hoàn tất! Đã gửi lệnh Renew Server thành công!")

        browser.close()

if __name__ == "__main__":
    main()
