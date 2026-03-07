import time
import os
import json
import sys
import gspread
from google.oauth2.service_account import Credentials

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

print("🚀 FAST GMB SCRAPER STARTED", flush=True)

# =========================
# GOOGLE SHEETS SETUP
# =========================
SCOPES = [
"https://www.googleapis.com/auth/spreadsheets",
"https://www.googleapis.com/auth/drive"
]

creds_raw = os.environ["GOOGLE_CREDS"]
creds_dict = json.loads(creds_raw)
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n","\n")

creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

sheet = client.open("Jaipur Gym With Phone").sheet1

if not sheet.get_all_values():
    sheet.append_row([
        "Name",
        "Phone",
        "Rating",
        "Reviews",
        "Address",
        "Maps Link"
    ])

print("✅ Google Sheets Connected", flush=True)

# =========================
# CHROME
# =========================
options = Options()

options.binary_location = "/usr/bin/chromium"

options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--disable-blink-features=AutomationControlled")

options.add_argument(
"user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
)

service = Service("/usr/bin/chromedriver")

driver = webdriver.Chrome(service=service, options=options)

print("🌍 Chrome started", flush=True)

# =========================
# AREAS
# =========================
AREAS = [
"Malviya Nagar Jaipur",
"Mansarovar Jaipur",
"Vaishali Nagar Jaipur",
"Jagatpura Jaipur",
"Tonk Road Jaipur",
"C Scheme Jaipur",
"Raja Park Jaipur"
]

KEYWORD = "gym"

# =========================
# SCRAPER
# =========================
for area in AREAS:

    search = f"{KEYWORD} in {area}"

    url = "https://www.google.com/maps/search/" + search.replace(" ","+")

    print("🔎 Searching:",search, flush=True)

    driver.get(url)

    time.sleep(8)

    links=set()

    for i in range(10):

        cards = driver.find_elements(By.CSS_SELECTOR,"a.hfpxzc")

        for c in cards:

            link = c.get_attribute("href")

            if link:
                links.add(link)

        driver.execute_script(
        "window.scrollTo(0, document.body.scrollHeight);")

        time.sleep(2)

    print("📊 Businesses found:",len(links), flush=True)

    for link in links:

        try:

            driver.get(link)

            time.sleep(3)

            name = driver.find_element(By.TAG_NAME,"h1").text

            try:
                phone = driver.find_element(
                By.XPATH,'//a[starts-with(@href,"tel:")]'
                ).text
            except:
                phone = ""

            try:
                rating = driver.find_element(
                By.CSS_SELECTOR,"div.F7nice span"
                ).text
            except:
                rating = ""

            try:
                reviews = driver.find_element(
                By.CSS_SELECTOR,"span[aria-label*='reviews']"
                ).text
            except:
                reviews = ""

            try:
                address = driver.find_element(
                By.XPATH,'//button[contains(@data-item-id,"address")]'
                ).text
            except:
                address = ""

            print("💾 Saving:",name, flush=True)

            sheet.append_row([
                name,
                phone,
                rating,
                reviews,
                address,
                link
            ])

        except Exception as e:

            print("⚠ Skip error:",str(e), flush=True)

driver.quit()

print("🛑 Scraper Finished", flush=True)
