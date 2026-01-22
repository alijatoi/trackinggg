from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import requests

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
    """Call GitHub API to disable this workflow so it never runs again."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    workflow_id = os.environ.get("GITHUB_WORKFLOW") # Usually the name of the workflow
    
    if not token or not repo:
        print("GitHub token or repository not found. Manual disable required.")
        return

    # To be safe, we list workflows to find the ID of 'Appointment Bot'
    url = f"https://api.github.com/repos/{repo}/actions/workflows"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            workflows = response.json().get('workflows', [])
            for w in workflows:
                if w['name'] == "Appointment Bot":
                    disable_url = f"https://api.github.com/repos/{repo}/actions/workflows/{w['id']}/disable"
                    res = requests.put(disable_url, headers=headers)
                    if res.status_code == 204:
                        print("Successfully disabled GitHub workflow permanently.")
                    else:
                        print(f"Failed to disable workflow: {res.status_code}")
                    break
    except Exception as e:
        print(f"Error disabling workflow: {e}")

def book_appointment():
    URL = os.environ.get("APPOINTMENT_URL", "https://tempus-termine.com/...")
    USER_DATA = {
        "Nachname": os.environ.get("MY_LAST_NAME", "Surname"),
        "Vorname": os.environ.get("MY_FIRST_NAME", "FirstName"),
        "Geburtsdatum": os.environ.get("MY_BIRTHDATE", "01.01.1990"), 
        "Telefonnummer": os.environ.get("MY_PHONE", "0123456789"),
        "E-Mail": os.environ.get("MY_EMAIL", "your_email@example.com"),
    }
    
    driver = setup_driver()
    wait = WebDriverWait(driver, 15)
    
    try:
        print(f"Navigating to {URL}")
        driver.get(URL)
        
        # 1. Select Earliest Date
        try:
             available_days = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "td.monatevent a")))
             if available_days:
                 available_days[0].click()
        except Exception:
            return False

        # 2. Select Earliest Time
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
            else:
                return False
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
                        repeat_email = driver.find_element(By.XPATH, "//input[@name='email2'] | //label[contains(., 'Wiederholung')]//input")
                        repeat_email.clear()
                        repeat_email.send_keys(value)
                    except: pass

        # Checkbox
        try:
            checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox' and contains(@name, 'datenschutz')]")
            if not checkbox.is_selected(): checkbox.click()
        except: pass

        # 4. Submit
        try:
            submit_btn = driver.find_element(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
            submit_btn.click()
        except: return False

        # 5. Success Detection
        time.sleep(5)
        success_keywords = ["Bestätigung", "Vielen Dank", "Reference", "Termin-ID", "gebucht"]
        page_text = driver.execute_script("return document.body.innerText")
        for keyword in success_keywords:
            if keyword.lower() in page_text.lower():
                print(f"!!! SUCCESS: Found keyword '{keyword}' !!!")
                return True
        if "confirm" in driver.current_url.lower() or "bestaetigung" in driver.current_url.lower():
            return True
        return False
    except: return False
    finally: driver.quit()

if __name__ == "__main__":
    print("Bot starting on GitHub Actions...")
    start_time = time.time()
    import random
    # Run for up to 280 seconds (Stay within one 5-minute GitHub trigger window)
    while time.time() - start_time < 280: 
        if book_appointment():
            print("Booking complete. Disabling future runs...")
            disable_github_workflow()
            exit(0)
        
        # Anti-spam: Wait about 1 minute between checks with some random variety
        wait_time = random.uniform(55, 65)
        print(f"No slot found. Waiting {int(wait_time)} seconds before next check...")
        time.sleep(wait_time)
