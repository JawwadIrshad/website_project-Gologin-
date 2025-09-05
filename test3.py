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
OUTPUT_CSV = "form_pages.csv" #output file with "url" column
WAIT_TIME = 5
KEYWORDS = ["contact", "get in touch", "reach us", "connect", "support", "help"]

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
    writer.writerow(["form_url", "form_fields"])  # header - removed main_url

# =========================
# FUNCTION TO CHECK FOR SPECIFIC FORM
# =========================
def has_target_form():
    """Check if the current page has the target form with Name, Phone, Email, Message fields"""
    try:
        # Look for forms
        forms = driver.find_elements(By.TAG_NAME, "form")
        if not forms:
            return False, ""
        
        for form in forms:
            # Get all input and textarea fields in the form
            inputs = form.find_elements(By.TAG_NAME, "input")
            textareas = form.find_elements(By.TAG_NAME, "textarea")
            all_fields = inputs + textareas
            
            # Check field names/placeholders for our target fields
            field_names = []
            name_field = False
            phone_field = False
            email_field = False
            message_field = False
            
            for field in all_fields:
                # Check by name, placeholder, or id
                name = field.get_attribute("name") or ""
                placeholder = field.get_attribute("placeholder") or ""
                field_id = field.get_attribute("id") or ""
                
                field_text = f"{name} {placeholder} {field_id}".lower()
                
                if any(term in field_text for term in ["name", "full name", "fullname"]):
                    name_field = True
                    field_names.append("Name")
                elif any(term in field_text for term in ["phone", "mobile", "number"]):
                    phone_field = True
                    field_names.append("Phone")
                elif any(term in field_text for term in ["email", "mail"]):
                    email_field = True
                    field_names.append("Email")
                elif any(term in field_text for term in ["message", "comment", "query"]):
                    message_field = True
                    field_names.append("Message")
            
            # If we have all four required fields, this is our target form
            if name_field and phone_field and email_field and message_field:
                return True, ", ".join(field_names)
                
        return False, ""
        
    except Exception as e:
        print(f"Error checking form: {e}")
        return False, ""

# =========================
# FUNCTION TO CHECK ALL NAVBAR LINKS
# =========================
def check_form_pages(url):
    results = []
    try:
        driver.get(url)
        time.sleep(2)

        # First check if the main page has the form
        has_form, fields = has_target_form()
        if has_form:
            # Only save the form URL (current URL), not the main URL
            results.append((driver.current_url, fields))
            return results

        # If not, look for contact links in the navigation
        links = driver.find_elements(By.TAG_NAME, "a")
        candidate_links = []

        for link in links:
            try:
                text = link.text.strip().lower()
                href = link.get_attribute("href")
                
                if href and any(keyword in text for keyword in KEYWORDS):
                    candidate_links.append((text, href))
            except:
                continue

        if not candidate_links:
            return results  # Empty results means no form found

        # Check each candidate link
        for text, href in candidate_links:
            try:
                driver.get(href)
                time.sleep(2)

                # Check if this page has our target form
                has_form, fields = has_target_form()
                if has_form:
                    # Only save the form URL, not the main URL
                    results.append((driver.current_url, fields))
                    break  # Found our form, no need to check other links

            except Exception as e:
                print(f"Error checking {href}: {e}")
                continue

    except Exception as e:
        print(f"Error processing {url}: {e}")

    return results

# =========================
# MAIN LOOP
# =========================
form_count = 0
for i, url in enumerate(urls):
    print(f"Processing {i+1}/{len(urls)}: {url}")
    
    results = check_form_pages(url)
    
    # Only save if we found a form
    if results:
        form_count += 1
        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row in results:
                writer.writerow(row)
        
        print(f"✅ Form found! ({form_count} so far)")

driver.quit()
print(f"🎯 Finished. Found {form_count} URLs with the forms. Results the saved in {OUTPUT_CSV} file")
