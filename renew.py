import os
import time
import requests
from playwright.sync_api import sync_playwright

TWOCAPTCHA_API_KEY = os.environ.get("TWOCAPTCHA_API_KEY")
ZAMPTO_EMAIL = os.environ.get("ZAMPTO_EMAIL")
ZAMPTO_PASSWORD = os.environ.get("ZAMPTO_PASSWORD")

def solve_turnstile(sitekey, page_url):
    print(f"[+] Đang gửi Sitekey ({sitekey}) tới 2Captcha...")
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

def check_and_solve_captcha_if_present(page):
    """Kiểm tra xem trang hiện tại có Cloudflare Turnstile không, nếu có thì giải."""
    page.wait_for_timeout(3000)
    sitekey = None
    try:
        turnstile_elem = page.query_selector("[data-sitekey]")
        if turnstile_elem:
            sitekey = turnstile_elem.get_attribute("data-sitekey")
        else:
            sitekey = page.evaluate('''() => {
                const iframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
                if (iframe) {
                    const match = iframe.src.match(/sitekey=([^&]+)/);
                    if (match) return match[1];
                }
                return null;
            }''')
    except Exception:
        pass

    if sitekey:
        print(f"[!] Phát hiện Cloudflare Turnstile (Sitekey: {sitekey}). Tiến hành giải...")
        token = solve_turnstile(sitekey, page.url)
        page.evaluate(f'''
            const el = document.querySelector('[name="cf-turnstile-response"]');
            if (el) el.value = "{token}";
        ''')
        page.wait_for_timeout(2000)
        return True
    return False

def main():
    if not TWOCAPTCHA_API_KEY or not ZAMPTO_EMAIL or not ZAMPTO_PASSWORD:
        raise ValueError("Thiếu biến môi trường TWOCAPTCHA_API_KEY, ZAMPTO_EMAIL hoặc ZAMPTO_PASSWORD!")

    os.makedirs("screenshots", exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = context.new_page()

        # BƯỚC 1: Truy cập thẳng trang Login
        login_url = "https://dash.zampto.net/login"
        print(f"[1] Đang truy cập trang Login: {login_url}")
        page.goto(login_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.screenshot(path="screenshots/1_login_page.png")

        # Giải Captcha ở trang Login nếu có
        check_and_solve_captcha_if_present(page)

        # BƯỚC 2: Điền thông tin Đăng nhập
        print("[2] Đang tìm và điền Email & Password...")
        email_selector = 'input[type="email"], input[name="email"], input[placeholder*="email" i]'
        pass_selector = 'input[type="password"], input[name="password"]'

        try:
            page.wait_for_selector(email_selector, timeout=15000)
        except Exception:
            page.screenshot(path="screenshots/error_no_email_input.png")
            raise Exception(f"Không tìm thấy form login tại {page.url}. Hãy tải Artifacts kiểm tra 1_login_page.png!")

        page.fill(email_selector, ZAMPTO_EMAIL)
        page.fill(pass_selector, ZAMPTO_PASSWORD)

        # BƯỚC 3: Nhấn nút Login
        print("[3] Nhấn nút 'Login'...")
        login_btn = page.locator('button[type="submit"], button:has-text("Login")').first
        login_btn.click()
        page.wait_for_timeout(5000)
        page.screenshot(path="screenshots/2_after_login.png")

        # BƯỚC 4: Chuyển sang trang chi tiết Server
        print("[4] Đang nhấn 'View Server'...")
        view_server_btn = page.locator('a:has-text("View Server"), button:has-text("View Server"), a[href*="server"]').first
        
        server_href = view_server_btn.get_attribute("href")
        if server_href:
            if not server_href.startswith("http"):
                server_href = "https://dash.zampto.net" + server_href
            page.goto(server_href, wait_until="domcontentloaded")
        else:
            view_server_btn.click()

        page.wait_for_timeout(4000)
        page.screenshot(path="screenshots/3_server_details.png")

        # BƯỚC 5: Giải Captcha trên trang Renew Server
        print("[5] Kiểm tra và giải Captcha Renew Server...")
        solved = check_and_solve_captcha_if_present(page)
        if not solved:
            print("[!] Không tìm thấy Captcha hoặc Captcha đã tự thông qua.")

        # BƯỚC 6: Nhấn Renew Server
        print("[6] Nhấn nút 'Renew Server'...")
        renew_btn = page.locator("button:has-text('Renew Server')").first
        renew_btn.click()

        page.wait_for_timeout(5000)
        page.screenshot(path="screenshots/4_renew_completed.png")
        print("[+] Hoàn tất! Đã gửi lệnh Renew Server thành công!")

        browser.close()

if __name__ == "__main__":
    main()
