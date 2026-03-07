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
from webdriver_manager.chrome import ChromeDriverManager

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

# 🔹 UPDATED: Load credentials from Railway environment variable
creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

client = gspread.authorize(creds)

sheet_with_phone = client.open(SHEET_WITH_PHONE_NAME).sheet1
sheet_no_phone = client.open(SHEET_NO_PHONE_NAME).sheet1

# Add headers if empty
if not sheet_with_phone.get_all_values():
    sheet_with_phone.append_row(["Name", "Profile Link", "Number Available"])

if not sheet_no_phone.get_all_values():
    sheet_no_phone.append_row(["Name", "Profile Link", "Number Available"])

# Create/Get SUMMARY sheet
try:
    summary_sheet = sheet_with_phone.spreadsheet.worksheet("SUMMARY")
except:
    summary_sheet = sheet_with_phone.spreadsheet.add_worksheet(
        title="SUMMARY", rows="20", cols="5"
    )

# Load existing links
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
# JAIPUR AREAS
# =========================
JAIPUR_AREAS = [
    "Adarsh Nagar","Agra Road","Agrasen Nagar","Ajmer Road","Albert Hall","Ambabari",
    "Amer","Anand Nagar","Bais Godam","Bani Park","Bapu Nagar","Barkat Nagar",
    "Bhatta Basti","Bhankrota","Bhawani Nagar","Bherunath Colony","Bindayaka",
    "Civil Lines","C Scheme","Chandpole","Chitrakoot","Dadu Dayal Nagar",
    "Dahar Ka Balaji","Dhanwantri Nagar","Dilwas","Fateh Tiba","Gandhi Nagar",
    "Ganga Jamuna Petrol Pump","Gopinath Marg","Goverdhanpura","Gulab Nagar",
    "Guru Nanakpura","Hathipura","Heerapura","Jagatpura","Jaisinghpura",
    "Jal Mahal","Jamnagar Colony","Jhotwara","Kalwar Road","Kamal Pokhar",
    "Kalu Ji Ka Mohalla","Kanti Modi Nagar","Kartarpura","Khajuri Kalan",
    "Khoh Nagorian","Lal Kothi","Malviya Nagar","Mansarovar","Mawata",
    "MI Road","Murlipura","Nehru Nagar","New Colony","New Sanganer Road",
    "Niwaru Road","Nursery Circle","Panch Batti","Panchyawala","Patrakar Colony",
    "Patel Nagar","Peetal Factory","Pratap Nagar","Preetam Nagar","Raja Park",
    "Rambagh","Ramchandrapura","Ramnagar Mod","Renwal","Sethi Colony",
    "Shastri Nagar","Shipra Path","Sikar Road","Sindhi Colony","Sitapura",
    "Sodala","Subhash Nagar","Sumer Nagar","Surya Nagar","Talera Colony",
    "Tonaklal","Triveni Nagar","Vaishali Nagar","Vasant Kunj","Vidyadhar Nagar"
]

KEYWORDS = [
    "Gym","Fitness Center","Fitness Studio","Workout Gym",
    "Bodybuilding Gym","CrossFit Gym","Yoga Studio","Zumba Classes",
    "Aerobics Classes","Personal Trainer","Weight Training Gym",
    "Cardio Gym","Ladies Gym","Men's Gym","24 Hour Gym",
    "Powerlifting Gym","Functional Training","HIIT Training"
]

# =========================
# PROGRESS SYSTEM
# =========================
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {"area_index": 0, "keyword_index": 0}

def save_progress(area_idx, keyword_idx):
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"area_index": area_idx, "keyword_index": keyword_idx}, f)

progress = load_progress()

# =========================
# UPDATE SUMMARY FUNCTION
# =========================
def update_summary():
    summary_sheet.clear()
    summary_sheet.append_rows([
        ["Metric","Value"],
        ["Total Profiles Found",total_found_global],
        ["With Phone",total_with_phone_global],
        ["No Phone",total_no_phone_global],
        ["Skipped Duplicates",total_skipped_global],
        ["Closed Businesses Skipped",total_closed_skipped],
        ["Reviews < 10 Skipped",total_low_review_skipped],
        ["No Review Data Skipped",total_no_review_skipped],
        ["Last Updated",datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    ])

# =========================
# DRIVER SETUP
# =========================
options = Options()

# 🔹 UPDATED FOR CLOUD
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

wait = WebDriverWait(driver, 15)

# =========================
# DETECTION FUNCTIONS
# =========================
def detect_phone():
    tel_elements = driver.find_elements(By.XPATH,'//a[starts-with(@href,"tel:")]')
    call_buttons = driver.find_elements(By.XPATH,'//button[contains(@aria-label,"Call")]')
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
# MAIN LOOP
# =========================
try:
    for area_idx in range(progress["area_index"], len(JAIPUR_AREAS)):
        area = JAIPUR_AREAS[area_idx]
        start_keyword = progress["keyword_index"] if area_idx == progress["area_index"] else 0

        for keyword_idx in range(start_keyword, len(KEYWORDS)):
            keyword = KEYWORDS[keyword_idx]

            query = f"{keyword} in {area} Jaipur"
            search_url = "https://www.google.com/maps/search/" + query.replace(" ","+")

            print(f"\n🔎 Searching: {query}")
            driver.get(search_url)
            time.sleep(3)

            try:
                results_panel = wait.until(
                    EC.presence_of_element_located((By.XPATH,'//div[@role="feed"]'))
                )
            except:
                continue

            profile_links = set()
            last_count = 0

            while True:
                cards = driver.find_elements(By.XPATH,'//a[contains(@href,"/maps/place/")]')
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
                total_found_global += 1

                if link in all_saved_links:
                    total_skipped_global += 1
                    continue

                driver.get(link)
                time.sleep(random.uniform(2,4))

                try:
                    name = driver.find_element(By.XPATH,'//h1').text.strip()
                except:
                    continue

                if is_closed():
                    print(f"⛔ Closed Skipped: {name}")
                    total_closed_skipped += 1
                    continue

                review_count = get_review_count()

                if review_count is None:
                    print(f"⚠ No Review Data Skipped: {name}")
                    total_no_review_skipped += 1
                    continue

                if review_count < MINIMUM_REVIEWS:
                    print(f"⭐ Reviews Less Than {MINIMUM_REVIEWS} Skipped ({review_count}): {name}")
                    total_low_review_skipped += 1
                    continue

                phone = detect_phone()

                if phone == "YES":
                    sheet_with_phone.append_row([name,link,phone])
                    total_with_phone_global += 1
                else:
                    sheet_no_phone.append_row([name,link,phone])
                    total_no_phone_global += 1

                all_saved_links.add(link)
                time.sleep(1)

            update_summary()
            save_progress(area_idx, keyword_idx + 1)

        save_progress(area_idx + 1, 0)

except KeyboardInterrupt:
    print("Stopped manually — progress saved.")

finally:
    driver.quit()
    update_summary()

    print("\n========== FINAL SUMMARY ==========")
    print(f"📊 Total Profiles Found: {total_found_global}")
    print(f"📱 Total WITH Phone: {total_with_phone_global}")
    print(f"❌ Total NO Phone: {total_no_phone_global}")
    print(f"⛔ Duplicates Skipped: {total_skipped_global}")
    print(f"🚫 Closed Skipped: {total_closed_skipped}")
    print(f"⭐ Reviews < {MINIMUM_REVIEWS} Skipped: {total_low_review_skipped}")
    print(f"⚠ No Review Data Skipped: {total_no_review_skipped}")
    print("===================================")
