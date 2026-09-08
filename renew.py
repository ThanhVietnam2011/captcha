import os
import time
import requests
from playwright.sync_api import sync_playwright

TWOCAPTCHA_API_KEY = os.environ.get("TWOCAPTCHA_API_KEY")
ZAMPTO_COOKIE = os.environ.get("ZAMPTO_COOKIE")
SERVER_ID = os.environ.get("ZAMPTO_SERVER_ID")  # ID server dạng #345-f8 hoặc UUID từ thông tin server

def solve_turnstile(sitekey, page_url):
    print("[+] Đang gửi yêu cầu giải Cloudflare Turnstile tới 2Captcha...")
    req_url = f"https://2captcha.com/in.php?key={TWOCAPTCHA_API_KEY}&method=turnstile&sitekey={sitekey}&pageurl={page_url}&json=1"
    res = requests.get(req_url).json()
    
    if res.get("status") != 1:
        raise Exception(f"Lỗi gửi 2Captcha: {res.get('request')}")
    
    request_id = res["request"]
    print(f"[+] ID Captcha: {request_id}. Đang chờ 2Captcha xử lý...")
    
    # Chờ kết quả từ 2Captcha (tối đa 2 phút)
    for _ in range(24):
        time.sleep(5)
        chk_url = f"https://2captcha.com/res.php?key={TWOCAPTCHA_API_KEY}&action=get&id={request_id}&json=1"
        chk_res = requests.get(chk_url).json()
        if chk_res.get("status") == 1:
            print("[+] Giải Captcha thành công!")
            return chk_res["request"]
            
    raise Exception("Hết thời gian chờ giải Captcha từ 2Captcha.")

def main():
    if not TWOCAPTCHA_API_KEY or not ZAMPTO_COOKIE:
        raise ValueError("Thiếu biến môi trường TWOCAPTCHA_API_KEY hoặc ZAMPTO_COOKIE!")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Khởi tạo context với Cookie đăng nhập Zampto
        context = browser.new_context()
        context.add_cookies([{
            "name": "zampto_session",  # Tên cookie phiên làm việc của Zampto
            "value": ZAMPTO_COOKIE,
            "domain": "dash.zampto.net",
            "path": "/"
        }])

        page = context.new_page()
        target_url = "https://dash.zampto.net/servers"
        print(f"[+] Đang truy cập: {target_url}")
        page.goto(target_url, wait_until="networkidle")

        # Tìm Turnstile sitekey trên giao diện
        turnstile_elem = page.wait_for_selector("[data-sitekey]", timeout=20000)
        sitekey = turnstile_elem.get_attribute("data-sitekey")
        print(f"[+] Tìm thấy Sitekey: {sitekey}")

        # Gửi sang 2Captcha giải lấy Response Token
        token = solve_turnstile(sitekey, page.url)

        # Chèn Token giải được vào ô input của Turnstile
        page.evaluate(f'''
            const el = document.querySelector('[name="cf-turnstile-response"]');
            if (el) el.value = "{token}";
        ''')

        # Click nút Renew Server
        print("[+] Đang nhấn nút Renew Server...")
        renew_button = page.locator("button:has-text('Renew Server')")
        renew_button.click()

        page.wait_for_timeout(5000)
        print("[+] Đã hoàn tất gửi lệnh gia hạn!")
        
        browser.close()

if __name__ == "__main__":
    main()
