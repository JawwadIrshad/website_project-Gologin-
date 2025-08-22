import time
import csv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# CONFIG
# =========================
INPUT_CSV = "results.csv"   # input file with "url" column
OUTPUT_CSV = "form_pages.csv"
WAIT_TIME = 5
KEYWORDS = ["about", "contact", "feedback", "support"]

# =========================
# BROWSER SETUP
# =========================
options = uc.ChromeOptions()
options.add_argument("--start-maximized")
driver = uc.Chrome(options=options)

# =========================
# READ INPUT CSV
# =========================
urls = []
with open(INPUT_CSV, newline='', encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        urls.append(row["url"])

print(f"✅ Loaded {len(urls)} URLs")

# =========================
# PREPARE OUTPUT CSV
# =========================
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["main_url", "link_text", "checked_url", "status"])  # header

# =========================
# FUNCTION TO CHECK ALL NAVBAR LINKS
# =========================
def check_form_pages(url):
    results = []
    try:
        driver.get(url)
        time.sleep(2)

        # get all links
        links = driver.find_elements(By.TAG_NAME, "a")
        candidate_links = []

        for link in links:
            text = link.text.strip().lower()
            href = link.get_attribute("href")
            if href and any(word in text for word in KEYWORDS):
                candidate_links.append((text, href))

        if not candidate_links:
            results.append((url, "", "", "No link found ❌"))
            return results

        for text, href in candidate_links:
            try:
                driver.get(href)
                time.sleep(2)

                # check for <form>
                try:
                    WebDriverWait(driver, WAIT_TIME).until(
                        EC.presence_of_element_located((By.TAG_NAME, "form"))
                    )
                    results.append((url, text, href, "Form found ✅"))
                except TimeoutException:
                    results.append((url, text, href, "No form ❌"))

            except Exception as e:
                results.append((url, text, href, f"Error: {str(e)}"))

    except Exception as e:
        results.append((url, "", "", f"Main Page Error: {str(e)}"))

    return results

# =========================
# MAIN LOOP
# =========================
for url in urls:
    results = check_form_pages(url)

    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in results:
            writer.writerow(row)

    print(f"✅ Processed {url} -> {len(results)} links checked")

driver.quit()
print(f"🎯 Finished. Results saved in {OUTPUT_CSV}")
