#!/usr/bin/env python3

import os
import shutil
from tempfile import NamedTemporaryFile
import sys
import uuid
import time
import argparse
import yaml
import pandas as pd
import threading

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementNotInteractableException

from tqdm import tqdm
from pathlib import Path

from joblib import Parallel, delayed
SUPPORTED_AIRLINES = ("qatar",)

screenshot_directory = Path('screenshots')

drivers = {}

class check(object):
    def __call__(self, driver):
        try:
            return driver.find_element(By.ID,"flightDetailForm_outbound:calendarInitiator_OutBound")
        except:
            pass
        
        try:
            return driver.find_element(By.XPATH,"//li[contains(., 'There are currently no flight options')]")
        except:
            return False
        return False


def qatar_search(driver, from_airport, to_airport, departure_date, return_date, travel_class, promo=""):
    WebDriverWait(driver, 300).until(
        EC.visibility_of_element_located((By.ID, "T7-from")))

    driver.implicitly_wait(1)
    from_element = driver.find_element_by_id("T7-from")
    from_element.clear()
    from_element.send_keys(from_airport)
    from_element.send_keys(Keys.DOWN)
    from_element.send_keys(Keys.RETURN)
    driver.implicitly_wait(0.5)

    to_element = driver.find_element_by_id("T7-to")
    to_element.clear()
    to_element.send_keys(to_airport)
    to_element.send_keys(Keys.DOWN)
    to_element.send_keys(Keys.RETURN)
    driver.implicitly_wait(0.5)

    departure_element = driver.find_element_by_id("T7-departure_1")
    departure_element.clear()
    departure_element.send_keys(departure_date.strftime('%d %b %Y'))
    driver.implicitly_wait(0.5)


    arrival_element = driver.find_element_by_id("T7-arrival_1")
    arrival_element.clear()
    arrival_element.send_keys(return_date.strftime('%d %b %Y'))
    driver.implicitly_wait(0.5)

    passengers_element = driver.find_element_by_id("T7-passengers")
    passengers_element.click()
    Select(driver.find_element_by_id('adults')).select_by_index(1)
    driver.implicitly_wait(0.5)


    promo_element = driver.find_element_by_id("T7-promo")
    promo_element.clear()
    promo_element.send_keys(promo)
    driver.implicitly_wait(0.5)

    search_element = driver.find_element_by_id("T7-search")
    search_element.click()
    driver.implicitly_wait(0.5)


    WebDriverWait(driver, 300).until(
        check()
    )

    try:
        driver.find_element(By.XPATH,"//li[contains(., 'There are currently no flight options')]")
        return "Таких полетов нет"
    except:
        pass

    try:
        driver.find_element_by_xpath("//span[text()='(Taxes only)']")
    except:
        return "Нет скидосов"
    

    price = driver.find_element_by_class_name("number").text
    return price


def qatar_search_executor(outbound_airport, destination_airport, start_date, end_date):

    import chromedriver_binary  # Adds chromedriver binary to path
    options = webdriver.ChromeOptions()
    from fake_useragent import UserAgent

    ua = UserAgent(cache=False)

    user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/82.0.4103.61 Safari/537.36'   
    options.add_argument('user-agent={0}'.format(user_agent))
    options.add_argument("--headless")

    driver = webdriver.Chrome(chrome_options=options)
    driver.set_window_size(2560, 1440)
    driver.get("https://www.qatarairways.com/en/homepage.html")
    try:
        price = qatar_search(
                driver=driver,
                from_airport=outbound_airport,
                to_airport=destination_airport,
                departure_date=start_date,
                return_date=end_date,
                travel_class='economy',
                promo=flight_options["promo"]
            )
    except Exception as exc:
        price = str(exc)

    screenshot_path = screenshot_directory / outbound_airport  / destination_airport 
    screenshot_path.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_path / f"{start_date.strftime('%d %b %Y')}-{end_date.strftime('%d %b %Y')}.png"
    driver.save_screenshot(str(screenshot_path))
    return price



def qatar_main(flight_options):
    # Parse dates
    outbound_airports = flight_options["outbound_airports"]
    destination_airports = flight_options["destination_airports"]
    start_outbound_date = datetime.strptime(flight_options["start_outbound_date"], "%Y-%m-%d")
    end_outbound_date = datetime.strptime(flight_options["end_outbound_date"], "%Y-%m-%d")
    
    df = pd.DataFrame(columns=["outbound_airport", "destination_airport", "start_date", "return_date", "price"])

    for outbound_airport in tqdm(outbound_airports, desc="Outbound airports"):
        for destination_airport in tqdm(destination_airports, desc="Destination airports"):
            for start_date in tqdm([start_outbound_date + timedelta(days=x) for x in range((end_outbound_date - start_outbound_date).days)], desc="Start dates"):
                end_dates = [start_date + timedelta(days=x) for x in range(7, 20)]
                results = Parallel(n_jobs=1)(delayed(qatar_search_executor)(outbound_airport, destination_airport, start_date, end_date) for end_date in tqdm(end_dates, desc="End dates"))
                for result, end_date in zip(results, end_dates):
                    if not result:
                        continue
                    df = df.append({"outbound_airport": outbound_airport, "destination_airport": destination_airport, "start_date": start_date, "return_date": end_date, "price": result}, ignore_index=True)
                df.to_csv('prices.csv', index=False)



if __name__ == "__main__":

    with open("config.yaml", mode='r') as f:
        flight_options = yaml.safe_load(f)

    # Headless execution
    os.environ['MOZ_HEADLESS_WIDTH'] = '2560' # workaround to set size correctly
    os.environ['MOZ_HEADLESS_HEIGHT'] = '1440'
    
    
    qatar_main(flight_options)
