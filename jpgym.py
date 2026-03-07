import time
import os
import json
import random
import sys
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
print("🚀 SCRAPER STARTED")
sys.stdout.reconfigure(encoding='utf-8')

# =========================
# CONFIG
# =========================
SHEET_WITH_PHONE_NAME = "Jaipur Gym With Phone"
SHEET_NO_PHONE_NAME = "Jaipur Gym No Phone"
PROGRESS_FILE = "progress_jaipur.json"
MINIMUM_REVIEWS = 10

# =========================
# GOOGLE SHEETS SETUP
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Load credentials from Railway variable
creds_raw = os.environ["GOOGLE_CREDS"]
creds_dict = json.loads(creds_raw)

# Fix newline formatting
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

sheet_with_phone = client.open(SHEET_WITH_PHONE_NAME).sheet1
sheet_no_phone = client.open(SHEET_NO_PHONE_NAME).sheet1

# Add headers
if not sheet_with_phone.get_all_values():
    sheet_with_phone.append_row(["Name", "Profile Link", "Number Available"])

if not sheet_no_phone.get_all_values():
    sheet_no_phone.append_row(["Name", "Profile Link", "Number Available"])

# Summary sheet
try:
    summary_sheet = sheet_with_phone.spreadsheet.worksheet("SUMMARY")
except:
    summary_sheet = sheet_with_phone.spreadsheet.add_worksheet(
        title="SUMMARY", rows="20", cols="5"
    )

saved_links_with_phone = set(sheet_with_phone.col_values(2))
saved_links_no_phone = set(sheet_no_phone.col_values(2))
all_saved_links = saved_links_with_phone.union(saved_links_no_phone)

# =========================
# GLOBAL COUNTERS
# =========================
total_found_global = 0
total_with_phone_global = 0
total_no_phone_global = 0
total_skipped_global = 0
total_closed_skipped = 0
total_low_review_skipped = 0
total_no_review_skipped = 0

# =========================
# DRIVER SETUP
# =========================
options = Options()

options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")

options.binary_location = "/usr/bin/chromium"

driver = webdriver.Chrome(options=options)

wait = WebDriverWait(driver, 15)

# =========================
# DETECTION FUNCTIONS
# =========================
def detect_phone():
    tel_elements = driver.find_elements(By.XPATH, '//a[starts-with(@href,"tel:")]')
    call_buttons = driver.find_elements(By.XPATH, '//button[contains(@aria-label,"Call")]')
    return "YES" if tel_elements or call_buttons else "NO"


def is_closed():
    try:
        elements = driver.find_elements(By.XPATH,
            "//*[contains(text(),'Temporarily closed') or contains(text(),'Permanently closed')]"
        )
        return True if elements else False
    except:
        return False


def get_review_count():
    try:
        review_elements = driver.find_elements(
            By.XPATH,
            '//span[@role="img" and contains(@aria-label,"review")]'
        )

        for el in review_elements:
            aria_text = el.get_attribute("aria-label")
            if aria_text:
                number = ''.join(filter(str.isdigit, aria_text))
                if number:
                    return int(number)

        return None

    except:
        return None


# =========================
# UPDATE SUMMARY
# =========================
def update_summary():
    summary_sheet.clear()
    summary_sheet.append_rows([
        ["Metric", "Value"],
        ["Total Profiles Found", total_found_global],
        ["With Phone", total_with_phone_global],
        ["No Phone", total_no_phone_global],
        ["Skipped Duplicates", total_skipped_global],
        ["Closed Businesses Skipped", total_closed_skipped],
        ["Reviews < 10 Skipped", total_low_review_skipped],
        ["No Review Data Skipped", total_no_review_skipped],
        ["Last Updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    ])


# =========================
# MAIN LOOP
# =========================
try:

    JAIPUR_AREAS = ["Malviya Nagar", "Mansarovar", "Vaishali Nagar", "Jagatpura"]
    KEYWORDS = ["Gym", "Fitness Center", "Workout Gym"]

    for area in JAIPUR_AREAS:
        for keyword in KEYWORDS:

            query = f"{keyword} in {area} Jaipur"
            search_url = "https://www.google.com/maps/search/" + query.replace(" ", "+")

            print(f"\n🔎 Searching: {query}")

            driver.get(search_url)
            time.sleep(3)

            try:
                results_panel = wait.until(
                    EC.presence_of_element_located((By.XPATH, '//div[@role="feed"]'))
                )
            except:
                continue

            profile_links = set()
            last_count = 0

            while True:

                cards = driver.find_elements(By.XPATH, '//a[contains(@href,"/maps/place/")]')

                for c in cards:
                    link = c.get_attribute("href")
                    if link:
                        profile_links.add(link.split("?")[0])

                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight",
                    results_panel
                )

                time.sleep(1.5)

                if len(profile_links) == last_count:
                    break

                last_count = len(profile_links)

            for link in profile_links:

                if link in all_saved_links:
                    continue

                driver.get(link)
                time.sleep(random.uniform(2, 4))

                try:
                    name = driver.find_element(By.XPATH, '//h1').text.strip()
                except:
                    continue

                if is_closed():
                    continue

                review_count = get_review_count()

                if review_count is None:
                    continue

                if review_count < MINIMUM_REVIEWS:
                    continue

                phone = detect_phone()

                if phone == "YES":
                    sheet_with_phone.append_row([name, link, phone])
                else:
                    sheet_no_phone.append_row([name, link, phone])

                all_saved_links.add(link)

                time.sleep(1)

            update_summary()

except KeyboardInterrupt:
    print("Stopped manually")

finally:
    driver.quit()


