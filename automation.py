import time
import csv
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# =========================
# CONFIG
# =========================
KEYWORDS_CSV = "keywords.csv"
RESULTS_CSV = "results.csv"
FORM_PAGES_CSV = "form_pages.csv"
SCROLL_PAUSE = 2
MAX_SCROLLS = 5
WAIT_TIME = 5
KEYWORDS = ["contact", "get in touch", "reach us", "connect", "support", "help"]

# =========================
# BROWSER SETUP
# =========================
options = uc.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = uc.Chrome(options=options)

# =========================
# NEW FUNCTIONS
# =========================
def perform_random_human_activity():
    """Simulate human-like actions (scrolling, moving, clicking)"""
    try:
        # Random scrolling
        for _ in range(random.randint(2, 5)):
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
            time.sleep(random.uniform(0.5, 2))

        # Random mouse movements & clicks
        elements = driver.find_elements(By.CSS_SELECTOR, "a, button, input")
        if elements:
            for _ in range(random.randint(1, 3)):
                el = random.choice(elements)
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", el)
                    time.sleep(random.uniform(0.5, 1.5))
                    el.click()
                    time.sleep(random.uniform(0.5, 1.5))
                    driver.back()
                    time.sleep(random.uniform(0.5, 2))
                except:
                    continue

    except Exception as e:
        print(f"Human-like activity error: {e}")

def set_fake_cookies(url):
    """Add fake cookies to look like a human user"""
    try:
        driver.get(url)
        time.sleep(2)
        driver.add_cookie({"name": "session_id", "value": str(random.randint(100000, 999999)), "path": "/", "secure": True})
        driver.add_cookie({"name": "visited_before", "value": "true", "path": "/"})
        print(f"🍪 Fake cookies added for {url}")
    except Exception as e:
        print(f"Failed to add cookies: {e}")

# =========================
# ORIGINAL FUNCTIONS
# =========================
def read_keywords():
    keywords = []
    with open(KEYWORDS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            keywords.append(row["keyword"])
    print(f"✅ Loaded {len(keywords)} keywords")
    return keywords

def scrape_google(keyword):
    urls = []
    driver.get("https://www.google.com/")
    time.sleep(2)
    search_box = driver.find_element(By.NAME, "q")
    search_box.clear()
    search_box.send_keys(keyword)
    search_box.send_keys(Keys.RETURN)
    time.sleep(3)

    for _ in range(MAX_SCROLLS):
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(SCROLL_PAUSE)

    results = driver.find_elements(By.CSS_SELECTOR, "a")
    for r in results:
        href = r.get_attribute("href")
        if href and "google.com" not in href:
            urls.append(href)

    return list(set(urls))

def save_results(data):
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["keyword", "url"])
        writer.writeheader()
        writer.writerows(data)
    print(f"✅ Saved {len(data)} URLs to {RESULTS_CSV}")

def read_results():
    urls = []
    with open(RESULTS_CSV, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            urls.append(row["url"])
    print(f"✅ Loaded {len(urls)} URLs from {RESULTS_CSV}")
    return urls

def has_target_form():
    try:
        forms = driver.find_elements(By.TAG_NAME, "form")
        if not forms:
            return False, ""
        for form in forms:
            inputs = form.find_elements(By.TAG_NAME, "input")
            textareas = form.find_elements(By.TAG_NAME, "textarea")
            all_fields = inputs + textareas

            name_field = phone_field = email_field = message_field = False

            for field in all_fields:
                name = field.get_attribute("name") or ""
                placeholder = field.get_attribute("placeholder") or ""
                field_id = field.get_attribute("id") or ""
                text = f"{name} {placeholder} {field_id}".lower()

                if any(term in text for term in ["name", "full name", "fullname"]):
                    name_field = True
                elif any(term in text for term in ["phone", "mobile", "number"]):
                    phone_field = True
                elif any(term in text for term in ["email", "mail"]):
                    email_field = True
                elif any(term in text for term in ["message", "comment", "query"]):
                    message_field = True

            if name_field and phone_field and email_field and message_field:
                return True, "Name, Phone, Email, Message"

        return False, ""
    except Exception as e:
        print(f"Error checking form: {e}")
        return False, ""

def check_form_pages(url):
    results = []
    try:
        set_fake_cookies(url)
        driver.get(url)
        time.sleep(2)
        perform_random_human_activity()

        has_form, fields = has_target_form()
        if has_form:
            results.append((driver.current_url, fields))
            return results

        links = driver.find_elements(By.TAG_NAME, "a")
        candidate_links = []

        for link in links:
            try:
                text = link.text.strip().lower()
                href = link.get_attribute("href")
                if href and any(keyword in text for keyword in KEYWORDS):
                    candidate_links.append(href)
            except:
                continue

        for href in candidate_links:
            try:
                set_fake_cookies(href)
                driver.get(href)
                time.sleep(2)
                perform_random_human_activity()
                has_form, fields = has_target_form()
                if has_form:
                    results.append((driver.current_url, fields))
                    break
            except Exception as e:
                print(f"Error checking {href}: {e}")

    except Exception as e:
        print(f"Error processing {url}: {e}")

    return results

def save_form_pages(results):
    with open(FORM_PAGES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["form_url", "form_fields"])
        writer.writerows(results)
    print(f"🎯 Saved {len(results)} form pages to {FORM_PAGES_CSV}")

# =========================
# MAIN SCRIPT
# =========================
if __name__ == "__main__":
    keywords = read_keywords()
    all_urls = []

    for kw in keywords:
        print(f"🔍 Searching: {kw}")
        urls = scrape_google(kw)
        print(f"   ➝ Found {len(urls)} URLs")
        for url in urls:
            all_urls.append({"keyword": kw, "url": url})

    save_results(all_urls)

    urls_to_check = read_results()
    found_forms = []

    for i, url in enumerate(urls_to_check):
        print(f"({i+1}/{len(urls_to_check)}) Checking {url}")
        results = check_form_pages(url)
        if results:
            found_forms.extend(results)
            print(f"✅ Form found ({len(found_forms)} total)")

    save_form_pages(found_forms)
    driver.quit()
    print("🚀 Done!")
