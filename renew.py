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

    # Tạo thư mục chứa ảnh chụp màn hình
    os.makedirs("screenshots", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        # Bước 1: Trang chủ https://zampto.net/
        home_url = "https://zampto.net/"
        print(f"[1] Đang truy cập trang chủ: {home_url}")
        page.goto(home_url, wait_until="networkidle")
        page.screenshot(path="screenshots/1_home_page.png")

        # Bước 2: Bấm nút "Login"
        print("[2] Đang nhấn nút 'Login' trên trang chủ...")
        login_link = page.locator('a:has-text("Login"), button:has-text("Login")').first
        login_link.click()
        page.wait_for_load_state("networkidle")
        page.screenshot(path="screenshots/2_login_page.png")

        # Bước 3: Điền Email, Mật khẩu và bấm nút Login
        print("[3] Đang điền Email và Password...")
        page.fill('input[type="email"], input[name="email"]', ZAMPTO_EMAIL)
        page.fill('input[type="password"], input[name="password"]', ZAMPTO_PASSWORD)
        
        login_button = page.locator('button[type="submit"], button:has-text("Login")').first
        login_button.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        page.screenshot(path="screenshots/3_after_login.png")

        # Bước 4: Bấm vào "View Server"
        print("[4] Đang nhấn nút 'View Server'...")
        view_server_btn = page.locator('a:has-text("View Server"), button:has-text("View Server"), :has-text("View Server")').first
        view_server_btn.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)
        page.screenshot(path="screenshots/4_server_details.png")

        # Bước 5: Quét lấy Turnstile Sitekey và giải Captcha
        print("[5] Đang tìm Turnstile Sitekey...")
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
            raise ValueError("Không tìm thấy Turnstile Sitekey trên trang!")

        print(f"[+] Tìm thấy Turnstile Sitekey: {sitekey}")
        token = solve_turnstile(sitekey, page.url)

        page.evaluate(f'''
            const el = document.querySelector('[name="cf-turnstile-response"]');
            if (el) el.value = "{token}";
        ''')

        # Bước 6: Nhấn nút "Renew Server"
        print("[6] Đang nhấn nút 'Renew Server'...")
        renew_button = page.locator("button:has-text('Renew Server')").first
        renew_button.click()

        page.wait_for_timeout(5000)
        page.screenshot(path="screenshots/5_renew_completed.png")
        print("[+] Hoàn tất! Đã gửi lệnh Renew Server thành công!")

        browser.close()

if __name__ == "__main__":
    main()
