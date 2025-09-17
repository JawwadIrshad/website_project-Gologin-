#Proxy.py
import time
import os
import csv
import random
import requests
import urllib.parse
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException, ElementClickInterceptedException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from seleniumwire import undetected_chromedriver as uc
import cv2
import pytesseract
from PIL import Image
import numpy as np
from selenium.webdriver.common.action_chains import ActionChains
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from io import BytesIO
import base64

# 1️⃣ Point pytesseract to your Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# =========================
# CONFIG
# =========================
BASE_PROFILE_DIR = "C:/ChromeProfiles"
KEYWORDS_CSV = "keywords.csv"
SPONSORED_RESULTS_CSV = "sponsored_results.csv"
ACTIVITY_LOG_CSV = "activity_log.csv"

WAIT_TIME = 3
SCROLL_PAUSE = 2
MAX_AD_PAGES_PER_KEYWORD = 5
DWELL_RANGE_SECONDS = (4, 10)
SERP_SCROLL_BATCHES = 3
ACTIVITY_ROTATION = ["Dwell", "Scroll", "Form", "Click"]

# Your proxy list
proxies = [] # put your proxies here

# =========================
# UTILITIES
# =========================
def read_keywords(path):
    kws = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                kw = row.get("keyword") or row.get("Keyword") or row.get("KW")
                if kw:
                    kw = kw.strip()
                    if kw:
                        kws.append(kw)
        print(f"✅ Loaded {len(kws)} keywords from {path}")
    except FileNotFoundError:
        print(f"❌ Keywords file not found: {path}")
    except Exception as e:
        print(f"❌ Error reading keywords: {e}")
    return kws

def save_sponsored_results(mapped):
    try:
        with open(SPONSORED_RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Sponsored URL"])
            for kw, urls in mapped.items():
                for u in sorted(urls):
                    writer.writerow([kw, u])
        print(f"💾 Saved {sum(len(v) for v in mapped.values())} URLs → {SPONSORED_RESULTS_CSV}")
    except Exception as e:
        print(f"❌ Error saving sponsored results: {e}")

def save_activity_log(logs):
    try:
        with open(ACTIVITY_LOG_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["URL", "Activity"])
            for log in logs:
                writer.writerow(log)
        print(f"💾 Saved {len(logs)} activity logs → {ACTIVITY_LOG_CSV}")
    except Exception as e:
        print(f"❌ Error saving activity log: {e}")

# =========================
# CAPTCHA SOLVING FUNCTIONS
# =========================
def solve_captcha_if_present(driver):
    try:
        # Handle reCAPTCHA checkbox
        try:
            checkbox = driver.find_element(By.XPATH, "//div[@class='recaptcha-checkbox-border']")
            actions = ActionChains(driver)
            actions.move_to_element(checkbox).click().perform()
            print("[INFO] Clicked reCAPTCHA checkbox.")
            time.sleep(5)
            return True
        except (NoSuchElementException, ElementClickInterceptedException):
            print("[INFO] No checkbox found.")
        
        # Handle image/text CAPTCHA
        try:
            captcha_element = driver.find_element(By.XPATH, "//img[contains(@src,'captcha') or contains(@src,'CAPTCHA')]")
            print(f"[INFO] Captcha element detected: {captcha_element}")
            captcha_src = captcha_element.get_attribute("src")
            print(f"[INFO] Captcha image detected: {captcha_src}")
            
            # Download and solve the CAPTCHA
            if captcha_src.startswith('data:image'):
                # Handle base64 encoded image
                img_data = captcha_src.split(',')[1]
                img = Image.open(BytesIO(base64.b64decode(img_data)))
                img_array = np.array(img)
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            else:
                # Handle URL-based image
                response = requests.get(captcha_src, timeout=10)
                img_array = np.array(bytearray(response.content), dtype=np.uint8)
            
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            # Preprocess the image
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.medianBlur(gray, 3)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)

            # OCR with Tesseract
            custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
            captcha_text = pytesseract.image_to_string(thresh, config=custom_config).strip()
            print(f"[INFO] Captcha OCR result: {captcha_text}")
            
            if captcha_text:
                # Try to find the input field
                input_selectors = [
                    "//input[@type='text' and contains(@name,'captcha')]",
                    "//input[@type='text' and contains(@id,'captcha')]",
                    "//input[@type='text']"
                ]
                
                for selector in input_selectors:
                    try:
                        input_field = driver.find_element(By.XPATH, selector)
                        input_field.clear()
                        input_field.send_keys(captcha_text)
                        input_field.send_keys(Keys.ENTER)
                        print("[INFO] Captcha submitted.")
                        time.sleep(5)
                        return True
                    except NoSuchElementException:
                        continue
                        
        except NoSuchElementException:
            print("[INFO] No image/text CAPTCHA found.")
        except Exception as e:
            print(f"[WARNING] Error processing image CAPTCHA: {e}")
            
    except Exception as e:
        print(f"[WARNING] Failed to solve captcha: {e}")
    
    return False

def detect_and_solve_captcha(driver):
    # Check for different types of CAPTCHAs
    captcha_selectors = [
        'iframe[src*="captcha"]',
        'iframe[src*="recaptcha"]',
        'div[class*="captcha"]',
        'div[class*="recaptcha"]',
        'img[src*="captcha"]',
        'img[src*="CAPTCHA"]',
        'input[type="checkbox"][id*="captcha"]',
        'input[type="checkbox"][name*="captcha"]'
    ]
    
    for selector in captcha_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"[INFO] Found CAPTCHA element with selector: {selector}")
                return solve_captcha(driver, elements[0])
        except Exception as e:
            print(f"[WARNING] Error checking selector {selector}: {str(e)}")
    
    print("[INFO] No CAPTCHA detected")
    return False

def solve_captcha(driver, captcha_element):
    try:
        # Try different solving strategies
        if captcha_element.tag_name == 'iframe' and ('recaptcha' in captcha_element.get_attribute('src') or 'captcha' in captcha_element.get_attribute('src')):
            # It's likely a reCAPTCHA
            return solve_recaptcha(driver, captcha_element)
        elif captcha_element.tag_name == 'img' and ('captcha' in captcha_element.get_attribute('src') or 'CAPTCHA' in captcha_element.get_attribute('src')):
            # It's an image CAPTCHA
            return solve_image_captcha(driver, captcha_element)
        elif (captcha_element.get_attribute('type') == 'checkbox' and 
              ('captcha' in captcha_element.get_attribute('id') or 'captcha' in captcha_element.get_attribute('name'))):
            # It's a checkbox CAPTCHA
            return solve_checkbox_captcha(driver, captcha_element)
        else:
            print(f"[INFO] Unknown CAPTCHA type: {captcha_element.tag_name}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to solve CAPTCHA: {str(e)}")
        return False

def solve_recaptcha(driver, iframe_element):
    """Solve reCAPTCHA challenges"""
    print("[INFO] Attempting to solve reCAPTCHA")
    try:
        # Switch to the iframe
        driver.switch_to.frame(iframe_element)
        
        # Look for the checkbox
        checkbox_selectors = [
            '.recaptcha-checkbox-border',
            '.recaptcha-checkbox',
            '#recaptcha-anchor'
        ]
        
        for selector in checkbox_selectors:
            try:
                checkbox = driver.find_elements(By.CSS_SELECTOR, selector)
                if checkbox:
                    print("[INFO] Clicking reCAPTCHA checkbox")
                    checkbox[0].click()
                    time.sleep(3)
                    
                    # Check if challenge appears
                    challenge_selectors = [
                        '.rc-imageselect-challenge',
                        '#rc-imageselect'
                    ]
                    
                    for challenge_selector in challenge_selectors:
                        try:
                            challenge = driver.find_elements(By.CSS_SELECTOR, challenge_selector)
                            if challenge:
                                print("[INFO] reCAPTCHA challenge detected")
                                # For advanced challenges, you might need a CAPTCHA solving service
                                break
                        except:
                            continue
                    
                    # Switch back to main content
                    driver.switch_to.default_content()
                    return True
            except:
                continue
        
        # Switch back to main content
        driver.switch_to.default_content()
        return False
    except Exception as e:
        print(f"[ERROR] Failed to solve reCAPTCHA: {str(e)}")
        try:
            driver.switch_to.default_content()
        except:
            pass
        return False

def solve_image_captcha(driver, img_element):
    """Solve image-based CAPTCHAs using OCR"""
    print("[INFO] Attempting to solve image CAPTCHA")
    try:
        # Get the image source
        img_src = img_element.get_attribute('src')
        
        if img_src.startswith('data:image'):
            # Handle base64 encoded image
            img_data = img_src.split(',')[1]
            img = Image.open(BytesIO(base64.b64decode(img_data)))
        else:
            # Handle URL-based image
            response = requests.get(img_src, timeout=10)
            img = Image.open(BytesIO(response.content))
        
        # Convert to OpenCV format
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        
        # Preprocess the image
        processed_img = preprocess_captcha(img_cv)
        
        # Try to extract text
        captcha_text = extract_text_from_image(processed_img)
        
        if captcha_text:
            # Find the input field and enter the text
            input_selectors = [
                "input[type='text'][name*='captcha']",
                "input[type='text'][id*='captcha']",
                "input[type='text']"
            ]
            
            for selector in input_selectors:
                try:
                    input_field = driver.find_element(By.CSS_SELECTOR, selector)
                    input_field.clear()
                    input_field.send_keys(captcha_text)
                    print(f"[INFO] Entered CAPTCHA text: {captcha_text}")
                    
                    # Look for a submit button
                    submit_selectors = [
                        "button[type='submit']",
                        "input[type='submit']",
                        "button:contains('Submit')",
                        "button:contains('Verify')"
                    ]
                    
                    for submit_selector in submit_selectors:
                        try:
                            submit_button = driver.find_element(By.CSS_SELECTOR, submit_selector)
                            submit_button.click()
                            time.sleep(2)
                            break
                        except:
                            continue
                    
                    return True
                except NoSuchElementException:
                    continue
        
        return False
    except Exception as e:
        print(f"[ERROR] Failed to solve image CAPTCHA: {str(e)}")
        return False

def preprocess_captcha(image):
    """Preprocess CAPTCHA image for better OCR results"""
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply thresholding
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Remove noise
    kernel = np.ones((2, 2), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    return cleaned

def extract_text_from_image(image):
    """Extract text from processed CAPTCHA image"""
    try:
        # Use Tesseract OCR with custom configuration
        custom_config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        text = pytesseract.image_to_string(image, config=custom_config).strip()
        print(f"[INFO] OCR extracted text: {text}")
        return text
    except Exception as e:
        print(f"[ERROR] OCR extraction failed: {str(e)}")
        return ""

def solve_checkbox_captcha(driver, checkbox_element):
    """Solve checkbox CAPTCHAs by clicking them"""
    print("[INFO] Attempting to solve checkbox CAPTCHA")
    try:
        checkbox_element.click()
        time.sleep(2)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to solve checkbox CAPTCHA: {str(e)}")
        return False

# =========================
# CHROME SETUP WITH PROXY
# =========================
def setup_driver(profile_index, proxy):
    profile_dir = os.path.join(BASE_PROFILE_DIR, f"Profile{profile_index}")
    os.makedirs(profile_dir, exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--log-level=3")
    options.add_argument("--ignore-certificate-errors")

    seleniumwire_options = {
        "proxy": {
            "http": f"http://{proxy['user']}:{proxy['pass']}@{proxy['ip']}:{proxy['port']}",
            "https": f"http://{proxy['user']}:{proxy['pass']}@{proxy['ip']}:{proxy['port']}",
            "no_proxy": "localhost,127.0.0.1"
        }
    }

    try:
        driver = uc.Chrome(options=options, seleniumwire_options=seleniumwire_options)
        wait = WebDriverWait(driver, 20)
        return driver, wait
    except Exception as e:
        print(f"❌ Failed to create driver: {e}")
        raise

def safe_execute_script(driver, script, max_retries=3):
    """Execute JavaScript with retry logic"""
    for attempt in range(max_retries):
        try:
            return driver.execute_script(script)
        except Exception as e:
            print(f"Script execution attempt {attempt+1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise e
            time.sleep(1)
    return None

# =========================
# GOOGLE SCRAPING FUNCTIONS
# =========================
def handle_google_consent_if_any(driver):
    try:
        consent_selectors = [
            "//button[.//div[text()='I agree']]",
            "//button[.='I agree']",
            "//button[.='Accept all']",
            "//div[@role='none']//button[.//span[contains(text(),'Accept')]]",
            "//button[contains(., 'I agree')]",
            "//button[contains(., 'Accept all')]",
        ]
        
        for selector in consent_selectors:
            try:
                btns = driver.find_elements(By.XPATH, selector)
                if btns:
                    driver.execute_script("arguments[0].click();", btns[0])
                    print("[INFO] Clicked consent button")
                    time.sleep(3)
                    break
            except:
                continue
    except Exception as e:
        print(f"[INFO] No consent button found or error clicking: {e}")

def open_google_search_results(driver, query):
    q = urllib.parse.quote_plus(query)
    search_url = f"https://www.google.com/search?q={q}"
    driver.get(search_url)
    time.sleep(3)
    solve_captcha_if_present(driver)
    handle_google_consent_if_any(driver)
    
def scroll_serp_for_ads(driver):
    last_height = safe_execute_script(driver, "return document.body.scrollHeight")
    for _ in range(SERP_SCROLL_BATCHES):
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.END)
        time.sleep(SCROLL_PAUSE)
        new_height = safe_execute_script(driver, "return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

def get_sponsored_urls_once(driver):
    urls = set()
    containers = []
    
    # Try different container selectors
    container_selectors = [
        "#tads",
        "#bottomads",
        "//div[@aria-label='Ads']",
        "//div[contains(@class, 'ads')]",
        "//div[contains(@class, 'ad')]",
        "//div[contains(text(), 'Sponsored')]/ancestor::div[1]",
        "//span[contains(text(), 'Sponsored')]/ancestor::div[1]"
    ]
    
    for selector in container_selectors:
        try:
            if selector.startswith("//"):
                elements = driver.find_elements(By.XPATH, selector)
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                
            if elements:
                containers.extend(elements)
        except:
            continue

    for c in containers:
        try:
            anchors = c.find_elements(By.XPATH, ".//a[@href]")
            for a in anchors:
                href = a.get_attribute("href")
                if href and "google.com" not in href:
                    urls.add(href)
        except:
            continue

    if not urls:
        try:
            ad_labels = driver.find_elements(By.XPATH, "//span[normalize-space()='Sponsored' or normalize-space()='Ad' or normalize-space()='Ads']")
            for label in ad_labels:
                try:
                    block = label.find_element(By.XPATH, "./ancestor::div[1]")
                    anchors = block.find_elements(By.XPATH, ".//a[@href]")
                    for a in anchors:
                        href = a.get_attribute("href")
                        if href and "google.com" not in href:
                            urls.add(href)
                except:
                    continue
        except:
            pass

    return list(urls)

def go_to_next_serp(driver):
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
        except:
            continue
    return False

def scrape_sponsored_for_keyword(driver, query, max_pages=MAX_AD_PAGES_PER_KEYWORD):
    open_google_search_results(driver, query)
    all_urls = set()
    page = 0
    
    while page < max_pages:
        page += 1
        scroll_serp_for_ads(driver)
        urls = get_sponsored_urls_once(driver)
        print(f"🪧 '{query}' → page {page}: {len(urls)} sponsored URLs found.")
        all_urls.update(urls)
        
        if not go_to_next_serp(driver):
            break
            
        # Check for CAPTCHA on new page
        solve_captcha_if_present(driver)
        
    return sorted(all_urls)

# =========================
# HUMAN-LIKE ACTIVITY
# =========================
def perform_random_activity(driver, urls, log):
    if not urls:
        return
        
    activity = random.choice(ACTIVITY_ROTATION)
    url = random.choice(urls)
    try:
        driver.get(url)
        solve_captcha_if_present(driver)
        dwell = random.randint(*DWELL_RANGE_SECONDS)
        time.sleep(dwell)
        log.append((url, activity))
        print(f"🧍 {activity} on {url} for {dwell}s")
    except Exception as e:
        print(f"❌ Error performing activity: {e}")

# =========================
# MAIN LOOP
# =========================
def main():
    keywords = read_keywords(KEYWORDS_CSV)
    if not keywords:
        print("❌ No keywords to process. Exiting.")
        return
        
    mapped_results = {}
    activity_log = []

    for idx, kw in enumerate(keywords):
        proxy = random.choice(proxies)
        try:
            driver, wait = setup_driver(idx % len(proxies), proxy)
            urls = scrape_sponsored_for_keyword(driver, kw)
            mapped_results[kw] = urls
            
            if urls:
                perform_random_activity(driver, urls, activity_log)
                
            driver.quit()
            time.sleep(random.randint(2, 5))
            
        except WebDriverException as e:
            print(f"❌ Error with keyword '{kw}': {e}")
        except Exception as e:
            print(f"❌ Unexpected error with keyword '{kw}': {e}")

    save_sponsored_results(mapped_results)
    save_activity_log(activity_log)
    print("✅ Scraping finished successfully.")

if __name__ == "__main__":
    main()
