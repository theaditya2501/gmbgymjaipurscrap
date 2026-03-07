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

sys.stdout.reconfigure(encoding='utf-8')

# =========================
# CONFIG
# =========================
SHEET_WITH_PHONE_NAME = "Jaipur Gym With Phone"
SHEET_NO_PHONE_NAME = "Jaipur Gym No Phone"
MINIMUM_REVIEWS = 10

# =========================
# GOOGLE SHEETS
# =========================
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

if not sheet_with_phone.get_all_values():
    sheet_with_phone.append_row(["Name","Profile Link","Number Available"])

if not sheet_no_phone.get_all_values():
    sheet_no_phone.append_row(["Name","Profile Link","Number Available"])

# =========================
# DRIVER
# =========================
print("🌍 Starting Chrome")

options = Options()

options.binary_location="/usr/bin/chromium"

options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--remote-debugging-port=9222")

service = Service("/usr/bin/chromedriver")

driver = webdriver.Chrome(service=service, options=options)

wait = WebDriverWait(driver,25)

print("✅ Chrome started")

# =========================
# FUNCTIONS
# =========================
def detect_phone():
    tel=driver.find_elements(By.XPATH,'//a[starts-with(@href,"tel:")]')
    call=driver.find_elements(By.XPATH,'//button[contains(@aria-label,"Call")]')
    return "YES" if tel or call else "NO"


def is_closed():
    elements=driver.find_elements(By.XPATH,
        "//*[contains(text(),'Temporarily closed') or contains(text(),'Permanently closed')]"
    )
    return True if elements else False


def get_review_count():
    reviews=driver.find_elements(By.XPATH,'//span[@role="img" and contains(@aria-label,"review")]')

    for r in reviews:
        text=r.get_attribute("aria-label")
        if text:
            number=''.join(filter(str.isdigit,text))
            if number:
                return int(number)

    return None


# =========================
# AREAS
# =========================
JAIPUR_AREAS=[
"Malviya Nagar",
"Mansarovar",
"Vaishali Nagar",
"Jagatpura"
]

KEYWORDS=[
"Gym",
"Fitness Center",
"Workout Gym"
]

saved_links=set()

# =========================
# FIND RESULTS PANEL
# =========================
def find_results_panel():

    for i in range(10):

        try:
            panel=driver.find_element(By.XPATH,'//div[@role="feed"]')
            return panel
        except:
            pass

        try:
            panel=driver.find_element(By.XPATH,'//div[contains(@class,"m6QErb")]')
            return panel
        except:
            pass

        time.sleep(2)

    return None


# =========================
# MAIN LOOP
# =========================
try:

    for area in JAIPUR_AREAS:

        for keyword in KEYWORDS:

            query=f"{keyword} in {area} Jaipur"

            print("🔎 Searching:",query)

            url="https://www.google.com/maps/search/"+query.replace(" ","+")

            driver.get(url)

            time.sleep(5)

            results_panel=find_results_panel()

            if results_panel is None:
                print("❌ Results panel not found")
                continue

            print("✅ Results panel detected")

            profile_links=set()

            last_count=0
            no_change=0

            while True:

                cards=driver.find_elements(By.XPATH,'//a[contains(@href,"/maps/place/")]')

                for c in cards:

                    link=c.get_attribute("href")

                    if link:
                        profile_links.add(link.split("?")[0])

                print("Profiles:",len(profile_links))

                driver.execute_script(
                    "arguments[0].scrollTop=arguments[0].scrollHeight",
                    results_panel
                )

                time.sleep(2)

                if len(profile_links)==last_count:
                    no_change+=1
                else:
                    no_change=0

                if no_change>=3:
                    break

                last_count=len(profile_links)

            print("Total profiles:",len(profile_links))

            for link in profile_links:

                if link in saved_links:
                    continue

                driver.get(link)

                time.sleep(random.uniform(2,4))

                try:
                    name=driver.find_element(By.XPATH,'//h1').text.strip()
                except:
                    continue

                if is_closed():
                    continue

                reviews=get_review_count()

                if reviews is None:
                    continue

                if reviews<MINIMUM_REVIEWS:
                    continue

                phone=detect_phone()

                print("Saving:",name,phone)

                if phone=="YES":
                    sheet_with_phone.append_row([name,link,phone])
                else:
                    sheet_no_phone.append_row([name,link,phone])

                saved_links.add(link)

                time.sleep(1)

except Exception as e:

    print("❌ ERROR:",str(e))

finally:

    driver.quit()

    print("🛑 Scraper stopped")
