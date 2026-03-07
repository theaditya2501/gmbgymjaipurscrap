import time
import os
import json
import random
import sys
import gspread
from google.oauth2.service_account import Credentials

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

print("🚀 SCRAPER STARTED")
print("🌍 Initializing environment...")

sys.stdout.reconfigure(encoding='utf-8')

# =========================
# CONFIG
# =========================
SHEET_WITH_PHONE_NAME = "Jaipur Gym With Phone"
SHEET_NO_PHONE_NAME = "Jaipur Gym No Phone"
MINIMUM_REVIEWS = 10

print("⚙️ Configuration loaded")

# =========================
# GOOGLE SHEETS
# =========================
print("🔑 Connecting to Google Sheets...")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_raw = os.environ["GOOGLE_CREDS"]
creds_dict = json.loads(creds_raw)

creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

sheet_with_phone = client.open(SHEET_WITH_PHONE_NAME).sheet1
sheet_no_phone = client.open(SHEET_NO_PHONE_NAME).sheet1

print("✅ Google Sheets connected")

if not sheet_with_phone.get_all_values():
    sheet_with_phone.append_row(["Name","Profile Link","Number Available"])
    print("📄 Created headers in WITH PHONE sheet")

if not sheet_no_phone.get_all_values():
    sheet_no_phone.append_row(["Name","Profile Link","Number Available"])
    print("📄 Created headers in NO PHONE sheet")

# =========================
# CHROME SETUP
# =========================
print("🌍 Starting Chrome browser...")

options = Options()

options.binary_location = "/usr/bin/chromium"

options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--disable-software-rasterizer")

options.add_argument(
"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
)

service = Service("/usr/bin/chromedriver")

driver = webdriver.Chrome(service=service, options=options)

wait = WebDriverWait(driver, 20)

print("✅ Chrome started successfully")

# =========================
# FUNCTIONS
# =========================
def detect_phone():

    print("📞 Checking for phone number...")

    tel = driver.find_elements(By.XPATH,'//a[starts-with(@href,"tel:")]')
    call = driver.find_elements(By.XPATH,'//button[contains(@aria-label,"Call")]')

    if tel or call:
        print("📞 Phone detected")
        return "YES"

    print("❌ No phone found")
    return "NO"


def is_closed():

    elements = driver.find_elements(By.XPATH,
        "//*[contains(text(),'Temporarily closed') or contains(text(),'Permanently closed')]"
    )

    if elements:
        print("⛔ Business is closed")
        return True

    return False


def get_review_count():

    reviews = driver.find_elements(By.XPATH,'//span[@role="img" and contains(@aria-label,"review")]')

    for r in reviews:

        text = r.get_attribute("aria-label")

        if text:
            number = ''.join(filter(str.isdigit,text))
            if number:
                print("⭐ Reviews:",number)
                return int(number)

    print("⚠ Could not read review count")
    return None


# =========================
# AREAS
# =========================
JAIPUR_AREAS = [
"Malviya Nagar",
"Mansarovar",
"Vaishali Nagar",
"Jagatpura"
]

KEYWORDS = [
"Gym",
"Fitness Center",
"Workout Gym"
]

saved_links=set()

# =========================
# MAIN LOOP
# =========================
try:

    print("🔁 Starting search loop...")

    for area in JAIPUR_AREAS:

        print("\n📍 AREA:",area)

        for keyword in KEYWORDS:

            query = f"{keyword} in {area} Jaipur"

            print("\n🔎 Searching:",query)

            url = "https://www.google.com/maps/search/"+query.replace(" ","+")

            print("🌐 Opening Google Maps page...")

            driver.get(url)

            print("⏳ Waiting for results to load...")

            time.sleep(8)

            try:
                wait.until(
                    EC.presence_of_element_located(
                        (By.XPATH,'//a[contains(@href,"/maps/place/")]')
                    )
                )
            except:
                print("❌ No results detected")
                continue

            print("📜 Scrolling results...")

            profile_links=set()

            last_count=0
            no_change=0

            while True:

                cards=driver.find_elements(By.XPATH,'//a[contains(@href,"/maps/place/")]')

                for c in cards:

                    link=c.get_attribute("href")

                    if link:
                        profile_links.add(link.split("?")[0])

                print("🔗 Profiles collected:",len(profile_links))

                driver.execute_script(
                    "window.scrollTo(0, document.body.scrollHeight);"
                )

                time.sleep(2)

                if len(profile_links)==last_count:
                    no_change+=1
                else:
                    no_change=0

                if no_change>=3:
                    break

                last_count=len(profile_links)

            print("📊 Total profiles found:",len(profile_links))

            for link in profile_links:

                if link in saved_links:
                    continue

                print("\n📂 Opening profile:",link)

                driver.get(link)

                time.sleep(random.uniform(2,4))

                try:
                    name=driver.find_element(By.XPATH,'//h1').text.strip()
                    print("🏷 Business name:",name)
                except:
                    print("⚠ Could not read business name")
                    continue

                if is_closed():
                    continue

                reviews=get_review_count()

                if reviews is None:
                    continue

                if reviews<MINIMUM_REVIEWS:
                    print("⭐ Skipped due to low reviews")
                    continue

                phone=detect_phone()

                print("💾 Saving to Google Sheet...")

                if phone=="YES":
                    sheet_with_phone.append_row([name,link,phone])
                else:
                    sheet_no_phone.append_row([name,link,phone])

                saved_links.add(link)

                print("✅ Saved successfully")

                time.sleep(1)

except Exception as e:

    print("❌ ERROR:",str(e))

finally:

    driver.quit()

    print("🛑 Scraper stopped")
