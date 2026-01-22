from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import requests
import random

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def disable_github_workflow():
    """Call GitHub API to disable this workflow permanently."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    
    if not token or not repo:
        print("CRITICAL: GitHub token or repository not found. Please disable manually immediately!", flush=True)
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    try:
        # 1. Find the workflow ID by name
        url = f"https://api.github.com/repos/{repo}/actions/workflows"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            workflows = response.json().get('workflows', [])
            for w in workflows:
                # Use "Appointment Bot" as the name matching the YAML 'name' field
                if w['name'] == "Appointment Bot":
                    # 2. Disable it
                    disable_url = f"https://api.github.com/repos/{repo}/actions/workflows/{w['id']}/disable"
                    res = requests.put(disable_url, headers=headers)
                    if res.status_code == 204:
                        print("SUCCESS: GitHub workflow has been DISABLED PERMANENTLY.", flush=True)
                    else:
                        print(f"FAILED to disable: {res.status_code} {res.text}", flush=True)
                    return
            print(f"WORKFLOW NOT FOUND: Could not find workflow with name 'Appointment Bot'.", flush=True)
    except Exception as e:
        print(f"ERROR calling GitHub API: {e}", flush=True)

def book_appointment():
    URL = os.environ.get("APPOINTMENT_URL")
    USER_DATA = {
        "Nachname": os.environ.get("MY_LAST_NAME", "Surname"),
        "Vorname": os.environ.get("MY_FIRST_NAME", "FirstName"),
        "Geburtsdatum": os.environ.get("MY_BIRTHDATE", "01.01.1990"), 
        "Telefonnummer": os.environ.get("MY_PHONE", "0123456789"),
        "E-Mail": os.environ.get("MY_EMAIL", "your_email@example.com"),
    }
    
    if not URL:
        print("ERROR: APPOINTMENT_URL secret is missing!", flush=True)
        return False

    driver = setup_driver()
    wait = WebDriverWait(driver, 15)
    
    try:
        print(f"Navigating to site...", flush=True)
        driver.get(URL)
        
        # 1. Select Date
        try:
             available_days = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "td.monatevent a, td.actualdate a")))
             if available_days:
                 available_days[0].click()
        except:
            return False

        # 2. Select Time
        try:
            time_selectors = ["//table[@class='termine']//a", "//span[@class='bl1b']/parent::a"]
            times = []
            for selector in time_selectors:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    times = [el for el in elements if el.is_displayed()]
                    if times: break
            if not times:
                times = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "table.termine a, span.bl1b")))
            if times:
                times[0].click()
            else: return False
        except: return False

        # 3. Fill Form
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        for label_text, value in USER_DATA.items():
            search_labels = [label_text]
            if "Telefon" in label_text: search_labels.extend(["Tel.", "Rufnummer"])
            if "Mail" in label_text: search_labels.extend(["Email", "E-Mail"])
            input_field = None
            for s_label in search_labels:
                field_selectors = [f"//label[contains(., '{s_label}')]//input", f"//span[contains(., '{s_label}')]/following::input[1]"]
                for selector in field_selectors:
                    try:
                        input_field = driver.find_element(By.XPATH, selector)
                        if input_field and input_field.is_displayed(): break
                    except: continue
                if input_field: break
            if input_field:
                input_field.clear()
                input_field.send_keys(value)
                if "Mail" in label_text:
                    try:
                        repeat = driver.find_element(By.XPATH, "//input[@name='email2'] | //label[contains(., 'Wiederholung')]//input")
                        repeat.clear()
                        repeat.send_keys(value)
                    except: pass

        # Privacy Checkbox
        try:
            cb = driver.find_element(By.XPATH, "//input[@type='checkbox' and contains(@name, 'datenschutz')]")
            if not cb.is_selected(): cb.click()
        except: pass

        # 4. Submit
        try:
            submit_btn = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
            submit_btn.click()
            print("Form submitted. Waiting for confirmation...", flush=True)
        except: return False

        # 5. Success Detection
        time.sleep(8)
        success_keywords = [
            "erfolgreich vereinbart", "Termin-Nummer", "Bestätigung", "Vielen Dank", 
            "Reference", "Termin-ID", "gebucht", "successfully", "confirmation"
        ]
        page_text = driver.execute_script("return document.body.innerText")
        current_url = driver.current_url.lower()
        
        if any(x in current_url for x in ["confirm", "bestaetigung", "appointment-success"]):
            print("!!! SUCCESS DETECTED BY URL !!!", flush=True)
            return True

        for keyword in success_keywords:
            if keyword.lower() in page_text.lower():
                print(f"!!! SUCCESS DETECTED BY KEYWORD: {keyword} !!!", flush=True)
                return True
        
        return False
    except Exception as e:
        print(f"Attempt failed: {e}", flush=True)
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    print("Bot starting on GitHub Actions...", flush=True)
    start_time = time.time()
    while time.time() - start_time < 280: 
        if book_appointment():
            print("BOOKING CONFIRMED! KILLING BOT FOREVER...", flush=True)
            disable_github_workflow()
            exit(0)
        
        wait_time = random.uniform(55, 65)
        print(f"Waiting {int(wait_time)}s...", flush=True)
        time.sleep(wait_time)
