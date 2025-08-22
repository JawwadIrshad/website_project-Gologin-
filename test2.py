import time
import csv
import random
import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# CONFIG
# =========================
INPUT_CSV = "results.csv"     # CSV input file with column "url"
OUTPUT_CSV = "form_results.csv"
SCREENSHOT_DIR = "screenshots"
WAIT_TIME = 8                 # wait time for elements
MAX_RETRIES = 2               # retries per URL

# ✅ Random User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0"
]

# =========================
# BROWSER FACTORY
# =========================
def create_driver(user_agent=None):
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    if user_agent:
        options.add_argument(f'--user-agent={user_agent}')
    return uc.Chrome(options=options)

# =========================
# READ URLS
# =========================
urls = []
with open(INPUT_CSV, newline='', encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        urls.append(row["url"])
print(f"✅ Loaded {len(urls)} URLs")

# =========================
# PREPARE OUTPUT
# =========================
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["url", "status"])

# =========================
# FORM HANDLER
# =========================
def try_fill_form(driver, url):
    try:
        # Scroll page
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight/3);")
            time.sleep(1)

        # Find first form
        form = WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.TAG_NAME, "form"))
        )

        # Fill common fields
        try:
            name_field = form.find_element(By.XPATH, ".//input[contains(@name,'name') or contains(@id,'name')]")
            name_field.send_keys("John Doe")
        except NoSuchElementException:
            pass

        try:
            email_field = form.find_element(By.XPATH, ".//input[contains(@type,'email') or contains(@name,'mail')]")
            email_field.send_keys("test@example.com")
        except NoSuchElementException:
            pass

        try:
            message_field = form.find_element(By.XPATH, ".//textarea")
            message_field.send_keys("Hello, this is a test message.")
        except NoSuchElementException:
            pass

        # Try to click submit
        try:
            submit_btn = form.find_element(By.XPATH, ".//button[@type='submit'] | .//input[@type='submit']")
            submit_btn.click()
            time.sleep(2)
        except NoSuchElementException:
            pass

        # Take screenshot
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"{int(time.time())}.png")
        driver.save_screenshot(screenshot_path)

        # Save success
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([url, f"Form filled ✅ (screenshot: {screenshot_path})"])

    except TimeoutException:
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([url, "No form found ❌"])

# =========================
# MAIN LOOP
# =========================
for url in urls:
    success = False
    for attempt in range(1, MAX_RETRIES + 1):
        ua = random.choice(USER_AGENTS)
        driver = create_driver(ua)

        try:
            driver.get(url)
            time.sleep(3)
            try_fill_form(driver, url)
            success = True
            break
        except Exception as e:
            print(f"⚠️ Error on {url} (attempt {attempt}): {e}")
            if attempt == MAX_RETRIES:
                with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([url, f"Error: {str(e)}"])
        finally:
            driver.quit()

    if not success:
        print(f"❌ Failed on {url} after {MAX_RETRIES} retries")

print(f"✅ Finished. Results in {OUTPUT_CSV}, screenshots in {SCREENSHOT_DIR}")
