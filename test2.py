#test2.py file
import time
import csv
import random
import urllib.parse
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    WebDriverException,
    TimeoutException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# CONFIG
# =========================
KEYWORDS_CSV = "keywords.csv"                     # input (must have column: keyword)
SPONSORED_RESULTS_CSV = "sponsored_results.csv"   # output
ACTIVITY_LOG_CSV = "activity_log.csv"             # Log the activities performed on URLs
WAIT_TIME = 3                                     # generic wait after loads
SCROLL_PAUSE = 2                                  # pause between SERP scrolls
MAX_AD_PAGES_PER_KEYWORD = 5                      # safety cap for depth
DWELL_RANGE_SECONDS = (4, 10)                     # dwell on a site before/after clicks
MAX_ACTIVITY_CLICKS_PER_SITE = (1, 3)             # random clicks per site
SERP_SCROLL_BATCHES = 3                           # how many times to scroll SERP to load ads

# =========================
# BROWSER SETUP
# =========================
options = uc.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless=new")  # ← uncomment if you want headless
driver = uc.Chrome(options=options)
wait = WebDriverWait(driver, 20)

# =========================
# UTILITIES
# =========================
def read_keywords(path):
    kws = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kw = row.get("keyword") or row.get("Keyword") or row.get("KW")
            if kw:
                kw = kw.strip()
                if kw:
                    kws.append(kw)
    print(f"✅ Loaded {len(kws)} keywords from {path}")
    return kws

def save_sponsored_results(mapped):
    with open(SPONSORED_RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Keyword", "Sponsored URL"])
        for kw, urls in mapped.items():
            for u in sorted(urls):
                writer.writerow([kw, u])
    print(f"💾 Saved {sum(len(v) for v in mapped.values())} URLs → {SPONSORED_RESULTS_CSV}")

def save_activity_log(logs):
    with open(ACTIVITY_LOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["URL", "Activity"])
        for log in logs:
            writer.writerow(log)
    print(f"💾 Saved {len(logs)} activity logs → {ACTIVITY_LOG_CSV}")

def handle_google_consent_if_any():
    """Try to accept Google consent dialogs."""
    try:
        # EU / regional consent variations
        candidates = [
            (By.XPATH, "//button[.//div[text()='I agree']]"),
            (By.XPATH, "//button[.='I agree']"),
            (By.XPATH, "//button[.='Accept all']"),
            (By.XPATH, "//div[@role='none']//button[.//span[contains(text(),'Accept')]]"),
            (By.XPATH, "//button[contains(., 'I agree')]"),
            (By.XPATH, "//button[contains(., 'Accept all')]"),
        ]
        for by, sel in candidates:
            btns = driver.find_elements(by, sel)
            if btns:
                try:
                    driver.execute_script("arguments[0].click();", btns[0])
                    time.sleep(3)
                    break
                except Exception:
                    pass
    except Exception:
        pass

def open_google_search_results(query):
    q = urllib.parse.quote_plus(query)
    search_url = f"https://www.google.com/search?q={q}"
    driver.get(search_url)
    handle_google_consent_if_any()
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#search")))

    except TimeoutException:
        time.sleep(WAIT_TIME)

def scroll_serp_for_ads():
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(SERP_SCROLL_BATCHES):
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(SCROLL_PAUSE)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def get_sponsored_urls_once():
    """
    Extract sponsored ad URLs from common ad containers.
    Tries multiple selectors for robustness against DOM changes.
    """
    urls = set()

    # Known containers
    containers = []
    for cid in ["tads", "bottomads"]:
        try:
            c = driver.find_element(By.ID, cid)
            containers.append(c)
        except NoSuchElementException:
            pass

    # ARIA label fallback
    if not containers:
        try:
            containers = driver.find_elements(By.XPATH, "//div[@aria-label='Ads']")
        except Exception:
            containers = []

    # Collect anchors within detected containers
    for c in containers:
        anchors = c.find_elements(By.XPATH, ".//a[@href]")
        for a in anchors:
            href = a.get_attribute("href")
            if href and "google.com" not in href:
                urls.add(href)

    # Last-resort heuristic (only if nothing found)
    if not urls:
        try:
            ad_labels = driver.find_elements(
                By.XPATH,
                "//span[normalize-space()='Sponsored' or normalize-space()='Ad' or normalize-space()='Ads']"
            )
            for label in ad_labels:
                try:
                    block = label.find_element(
                        By.XPATH,
                        "./ancestor::div[contains(@class,'ads') or contains(@class,'ad') or @aria-label='Ads']"
                    )
                    anchors = block.find_elements(By.XPATH, ".//a[@href]")
                    for a in anchors:
                        href = a.get_attribute("href")
                        if href and "google.com" not in href:
                            urls.add(href)
                except Exception:
                    continue
        except Exception:
            pass

    return list(urls)

def go_to_next_serp():
    candidates = [
        (By.ID, "pnnext"),
        (By.XPATH, "//a[@id='pnnext']"),
        (By.XPATH, "//a[@aria-label='Next']"),
        (By.XPATH, "//a[.//span[text()='Next']]"),
    ]
    for by, sel in candidates:
        try:
            nxt = driver.find_element(by, sel)
            driver.execute_script("arguments[0].click();", nxt)
            time.sleep(WAIT_TIME)
            return True
        except Exception:
            continue
    return False

def scrape_sponsored_for_keyword(query, max_pages=MAX_AD_PAGES_PER_KEYWORD):
    open_google_search_results(query)
    all_urls = set()
    page = 0

    while True:
        page += 1
        scroll_serp_for_ads()
        urls = get_sponsored_urls_once()
        print(f"🪧 '{query}' → page {page}: {len(urls)} sponsored URLs found.")
        all_urls.update(urls)

        if page >= max_pages:
            break
        if not go_to_next_serp():
            break

    return sorted(all_urls)

# =========================
# HUMAN-LIKE ACTIVITY + FAKE COOKIES
# =========================
def set_fake_cookies_for_current_domain():
    """
    Adds a couple of benign cookies to the CURRENT domain.
    Must be called AFTER driver.get(url) (same-domain restriction).
    Refresh to apply.
    """
    try:
        driver.add_cookie({"name": "session_id", "value": str(random.randint(100000, 999999)), "path": "/", "secure": True})
        driver.add_cookie({"name": "visited_before", "value": "true", "path": "/"})
        driver.refresh()
        print("🍪 Fake cookies set & page refreshed")
    except Exception as e:
        print(f"⚠️ Failed to set cookies: {e}")

# =========================
# HUMAN-ACTIVITY ROTATION
# =========================
ACTIVITY_ROTATION = ["Dwell", "Scroll", "Form", "Click"]  # order of rotation

def fill_form():
    """
    Attempts to find and fill a simple form on the page.
    Returns True if a form was found and submitted, False otherwise.
    """
    try:
        forms = driver.find_elements(By.TAG_NAME, "form")
        for form in forms:
            inputs = form.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='email']")
            for inp in inputs:
                inp.clear()
                inp.send_keys("test@example.com")
            submit_buttons = form.find_elements(By.CSS_SELECTOR, "input[type='submit'], button[type='submit'], button")
            if submit_buttons:
                submit_buttons[0].click()
                time.sleep(1)
                return True
        return False
    except Exception:
        return False

def perform_rotated_activity_on_url(url, activity_type):
    """Perform a single human-like action on the URL based on rotation."""
    activities = []

    # tiny dwell before activity to look human
    time.sleep(random.uniform(1, 2))

    if activity_type == "Dwell":
        time.sleep(random.uniform(*DWELL_RANGE_SECONDS))
        activities.append("Dwell")

    elif activity_type == "Scroll":
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.PAGE_DOWN)
            time.sleep(random.uniform(0.5, 1.2))
            activities.append("Scrolled")
        except Exception:
            activities.append("Scroll Failed")

    elif activity_type == "Form":
        if fill_form():
            activities.append("Form Submitted")
        else:
            activities.append("Form Not Found")

    elif activity_type == "Click":
        elements = driver.find_elements(
            By.CSS_SELECTOR,
            "a, button, input[type='button'], input[type='submit']"
        )
        random.shuffle(elements)
        if elements:
            el = elements[0]
            try:
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(random.uniform(0.3, 1.0))
                el.click()
                time.sleep(random.uniform(1.0, 2.0))
                activities.append("Clicked")
            except WebDriverException:
                activities.append("Click Failed")
        else:
            activities.append("No Elements to Click")

    # tiny dwell after activity
    time.sleep(random.uniform(1, 2))
    return activities

def visit_urls_with_activity(urls):
    logs = []
    uniq = []
    seen = set()
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)

    print(f"🧭 Visiting {len(uniq)} unique sponsored URLs with cookies + random activity...")
    for i, u in enumerate(uniq, 1):
        print(f"   ({i}/{len(uniq)}) {u}")
        try:
            driver.get(u)
            time.sleep(random.uniform(2, 4))
            set_fake_cookies_for_current_domain()

            # Determine which activity to perform based on rotation
            activity_type = ACTIVITY_ROTATION[i % len(ACTIVITY_ROTATION)]
            activities = perform_rotated_activity_on_url(u, activity_type)

            logs.append([u, ', '.join(activities)])

        except Exception as e:
            print(f"   ✖ Visit failed: {u} | {e}")
    return logs

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    try:
        keywords = read_keywords(KEYWORDS_CSV)

        # 1) Scrape sponsored URLs for each keyword
        results_map = {}
        for kw in keywords:
            print(f"\n🔍 Scraping sponsored ads for: {kw}")
            urls = scrape_sponsored_for_keyword(kw)
            results_map[kw] = urls
            print(f"✅ '{kw}': {len(urls)} unique sponsored URLs")

        # 2) Save to CSV
        save_sponsored_results(results_map)

        # 3) Visit each collected URL, set fake cookies, act like a human, and log activities
        all_urls = []
        for lst in results_map.values():
            all_urls.extend(lst)

        logs = visit_urls_with_activity(all_urls)
        save_activity_log(logs)

        print("\n🚀 Done!")
    finally:
        try:
            driver.quit()
        except Exception:
            pass
