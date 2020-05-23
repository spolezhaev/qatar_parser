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
from selenium.webdriver.chrome.options import Options

from tqdm import tqdm
from pathlib import Path

from joblib import Parallel, delayed
SUPPORTED_AIRLINES = ("qatar",)

screenshot_directory = Path('screenshots')

drivers = {}

class element_has_css_class(object):
    """An expectation for checking that an element has a particular css class.

    locator - used to find the element
    returns the WebElement once it has the particular css class
    """
    def __init__(self):
        pass

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
        # lambda driver: driver.find_element(By.ID, "T7-from") \
        #                 and driver.find_element(By.ID, "T7-to") \
        #                 and driver.find_element(By.ID, "T7-departure_1") \
        #                 and driver.find_element(By.ID, "T7-arrival_1") \
        #                 and driver.find_element(By.ID, "T7-promo")
    #)
    from_element = driver.find_element_by_id("T7-from")
    from_element.clear()
    from_element.send_keys(from_airport)
    from_element.send_keys(Keys.DOWN)
    from_element.send_keys(Keys.RETURN)

    to_element = driver.find_element_by_id("T7-to")
    to_element.clear()
    to_element.send_keys(to_airport)
    to_element.send_keys(Keys.DOWN)
    to_element.send_keys(Keys.RETURN)

    departure_element = driver.find_element_by_id("T7-departure_1")
    departure_element.clear()
    departure_element.send_keys(departure_date.strftime('%d %b %Y'))

    arrival_element = driver.find_element_by_id("T7-arrival_1")
    arrival_element.clear()
    arrival_element.send_keys(return_date.strftime('%d %b %Y'))

    passengers_element = driver.find_element_by_id("T7-passengers")
    passengers_element.click()
    Select(driver.find_element_by_id('adults')).select_by_index(1)
    #driver.find_element_by_xpath("//span[text()='1']").click()
    #driver.find_element_by_xpath("//span[text()='2']").click()


    promo_element = driver.find_element_by_id("T7-promo")
    promo_element.clear()
    promo_element.send_keys(promo)

    search_element = driver.find_element_by_id("T7-search")
    search_element.click()


    WebDriverWait(driver, 300).until(
        #lambda driver: driver.find_element(By.XPATH,"//li[text()='(There are currently no flight )']") or driver.find_element(By.ID,"flightDetailForm_outbound:calendarInitiator_OutBound")
        element_has_css_class()#EC.visibility_of_element_located((By.ID, "modifySearch"))# "flightDetailForm_outbound:calendarInitiator_OutBound"))
    )

    try:
        driver.find_element(By.XPATH,"//li[contains(., 'There are currently no flight options')]")
        return "Таких полетов нет"
    except:
        pass

    # #sort by price
    # price_element.click()
    #WebDriverWait(driver, 2)
    #driver.implicitly_wait(4)
    try:
        driver.find_element_by_xpath("//span[text()='(Taxes only)']")
    except:
        return "Нет скидосов"
    

    price = driver.find_element_by_class_name("number").text
    #print(driver.find_element_by_class_name("number").text)
    return price


def qatar_search_executor(outbound_airport, destination_airport, start_date, end_date):
    # create driver
    # Global driver variable

    # tmp_name = f"geckodrivers/{uuid.uuid1()}"
    # with open("geckodriver", 'rb') as src, open(tmp_name, 'wb+') as dst: dst.write(src.read())

    # #umask = os.umask(0)
    # #os.umask(umask)
    # os.chmod(tmp_name, 0o777)
    # try:
    #     driver = drivers[threading.current_thread().name]
    # except KeyError:
    #     drivers[threading.current_thread().name] = webdriver.Firefox(executable_path=os.path.abspath(tmp_name), options=options)
    #     driver = drivers[threading.current_thread().name]
    import chromedriver_binary  # Adds chromedriver binary to path

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
        price = None

    screenshot_path = screenshot_directory / outbound_airport  / destination_airport 
    screenshot_path.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_path / f"{start_date.strftime('%d %b %Y')}-{end_date.strftime('%d %b %Y')}.png"
    driver.save_screenshot(str(screenshot_path))
    #os.remove(tmp_name)
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
                results = Parallel(n_jobs=2)(delayed(qatar_search_executor)(outbound_airport, destination_airport, start_date, end_date) for end_date in tqdm(end_dates, desc="End dates"))
                for result, end_date in zip(results, end_dates):
                    if not result:
                        continue
                    df = df.append({"outbound_airport": outbound_airport, "destination_airport": destination_airport, "start_date": start_date, "return_date": end_date, "price": result}, ignore_index=True)
                df.to_csv('prices.csv', index=False)



if __name__ == "__main__":

    with open("config.yaml", mode='r') as f:
        flight_options = yaml.safe_load(f)

    # Headless execution
    options = Options()
    user_agent = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.50 Safari/537.36'   
    options.headless = True
    options.add_argument('user-agent={0}'.format(user_agent))
    options.add_argument("--headless")
    os.environ['MOZ_HEADLESS_WIDTH'] = '2560' # workaround to set size correctly
    os.environ['MOZ_HEADLESS_HEIGHT'] = '1440'
    
    
    qatar_main(flight_options)
