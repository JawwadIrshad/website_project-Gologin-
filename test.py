#test.py
import time
import csv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# =========================
# CONFIG
# =========================
INPUT_CSV = "keywords.csv"     # Input file with keywords
OUTPUT_CSV = "results.csv"     # Output file for collected URLs
SCROLL_PAUSE = 2               # seconds pause after each scroll
MAX_SCROLLS = 5                # how many times to scroll down

# BROWSER SETUP
options = uc.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = uc.Chrome(options=options)

# =========================
# READ KEYWORDS FROM CSV
# =========================
keywords = []
with open(INPUT_CSV, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        keywords.append(row["keyword"])  # assumes CSV has "keyword" column

print(f"✅ Loaded {len(keywords)} keywords")

# =========================
# SCRAPING FUNCTION
# =========================
def scrape_google(keyword):
    urls = []

    driver.get("https://www.google.com/")
    time.sleep(2)

    # Search for keyword
    search_box = driver.find_element(By.NAME, "q")
    search_box.clear()
    search_box.send_keys(keyword)
    search_box.send_keys(Keys.RETURN)
    time.sleep(3)

    # Scroll multiple times
    for i in range(MAX_SCROLLS):
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(SCROLL_PAUSE)

    # Collect all search result URLs
    results = driver.find_elements(By.CSS_SELECTOR, "a")
    for r in results:
        href = r.get_attribute("href")
        if href and "google.com" not in href:
            urls.append(href)

    return list(set(urls))  # remove duplicates

# =========================
# MAIN LOOP
# =========================
all_data = []

for keyword in keywords:
    print(f"🔍 Searching for: {keyword}")
    urls = scrape_google(keyword)
    print(f"   ➝ Found {len(urls)} URLs")
    for url in urls:
        all_data.append({"keyword": keyword, "url": url})

# =========================
# SAVE TO CSV
# =========================
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["keyword", "url"])
    writer.writeheader()
    writer.writerows(all_data)

print(f"✅ Done! Saved {len(all_data)} rows in {OUTPUT_CSV}")
driver.quit()
