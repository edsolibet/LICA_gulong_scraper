# -*- coding: utf-8 -*-
"""
Created on Wed Aug  3 11:32:29 2022

@author: carlo
"""
import sys
import subprocess
import pkg_resources

required = {'pandas', 'numpy', 'selenium', 'parsel', 'datetime', 'webdriver_manager'}
installed = {pkg.key for pkg in pkg_resources.working_set}
missing = required - installed

if missing:
    python = sys.executable
    subprocess.check_call([python, '-m', 'pip', 'install', *missing], stdout=subprocess.DEVNULL)

import pandas as pd
import numpy as np
from datetime import datetime
import datetime as date
import re, os, sys, platform, string, time

import streamlit as st

import selenium
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from webdriver_manager.firefox import GeckoDriverManager
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver import ActionChains
from parsel import Selector

# to run selenium in headless mode (no user interface/does not open browser)
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')


def get_num_items(driver, xpath, site = 'gulong'):
    '''
    
    Parameters
    ----------
    driver : selenium
        Chrome driver
    xpath : string
        HTML xpath string for number of products
    site : string, optional
        Which site is being scraped. The default is 'gulong'.
        
    
    Returns
    -------
    
    '''
    total_items_text = driver.find_elements(By.XPATH, xpath)
    total_items_list = [items.text for items in total_items_text]
    if site=='gulong':
        total_items = [item for item in total_items_list[1].split(' ') if item.isdigit()][-1]
    elif site=='gogulong':
        total_items = [item for item in total_items_list[0].split(' ') if item.isdigit()][0]
    return total_items

def scrape_data(driver, data_list, xpath_info, site ='gulong'):
    '''

    Parameters
    ----------
    driver : selenium
        chrome driver
    data_list : list
        list of lists for scraped info (tires, price, info)
    xpath : dictionary
        Dictionary of tires, price, info html xpaths separated by website
    site : string, optional
        Which site is being scraped. The default is 'gulong'.

    Returns
    -------
    list
        list of lists containing text of scraped info (tire, price, info)

    '''
    tire_list_gulong, price_list_gulong, info_list_gulong = data_list
    # tires
    tires_gulong = driver.find_elements_by_xpath(xpath_info['tires'])
    # prices
    price_gulong = driver.find_elements_by_xpath(xpath_info['price'])
    # specs
    info_gulong = driver.find_elements_by_xpath(xpath_info['info'])
    # save scraped text
    for i in range(len(price_gulong)):
        if tires_gulong[i].text == '':
            continue
        else:
            if site =='gulong':
                tire_list_gulong.append(tires_gulong[i*2].text)
                price_list_gulong.append(price_gulong[i].text)
                info_list_gulong.append(info_gulong[i*2+1].text)
            else:
                tire_list_gulong.append(tires_gulong[i].text)
                price_list_gulong.append(price_gulong[i].text)
                info_list_gulong.append(info_gulong[i].text)

    return [tire_list_gulong, price_list_gulong, info_list_gulong]

def cleanup_specs(specs, col):
    '''
    Parameters
    ----------
    specs : string
        String to obtain specs info
    col : string
        Column name to apply function ('width', 'aspect_ratio', 'diameter')

    Returns
    -------
    specs : string
        Corresponding string value in specs to "col"

    '''
    specs_len = len(specs.split('/'))
    if specs_len == 1:
        return specs.split('/')[0]
    else:
        if col == 'width':
            return specs.split('/')[0]
        elif col == 'aspect_ratio':
            if specs.split('/')[1] == '0' or specs.split('/')[1] == '':
                return 'R'
            else:
                return specs.split('/')[1]
        elif col == 'diameter':
            return specs.split('/')[2][1:3]
        else:
            return specs

def combine_specs(row):
    '''
    Helper function to join corrected specs info

    Parameters
    ----------
    row : dataframe row
        From gogulong dataframe
    Returns
    -------
    string
        joined corrected specs info

    '''
    return '/'.join([row['width'], row['aspect_ratio'], row['diameter']])


def gulong_scraper(driver, xpath_prod, save=True):
    '''
    Gulong price scraper
    
    Parameters
    ----------
    driver : selenium
        Chrome driver
    xpath_prod : dictionary
        Dictionary of tires, price, info html xpaths separated by website
    save : bool, optional
        True if save result to csv. The default is True.

    Returns
    -------
    df_gulong : dataframe
        Dataframe containing scraped info

    '''
    print ('Starting scraping for Gulong.ph')
    url_page = 'https://gulong.ph/shop?page=1'
    driver.get(url_page)
    num_items = get_num_items(driver, xpath = '//span[@class="top-0 left-4 text-sm gulong-font"]', site='gulong')
    
    # calculate number of pages
    last_page = int(np.ceil(int(num_items)/24))
    last_page=5
    tire_list, price_list, info_list = [], [], []
    # iterate over product pages
    for page in range(last_page):
        url_page = 'https://gulong.ph/shop?page=' + str(page+1)
        driver.get(url_page)
        print("Getting info from Page: {}".format(page+1))
        tire_list_gulong, price_list_gulong, info_list_gulong = scrape_data(driver, 
                        [tire_list, price_list, info_list], xpath_prod['gulong'])
    
    # create dataframe
    df_gulong = pd.DataFrame({'name': tire_list_gulong, 'price': price_list_gulong, 'specs': info_list_gulong})
    
    # data cleaning and engineering
    df_gulong = df_gulong[df_gulong.loc[:,'specs'] != 'Promo']
    df_gulong.loc[:,'brand'] = df_gulong.loc[:,'specs'].apply(lambda x: x.split(' ')[0]) 
    df_gulong.loc[:,'specs'] = df_gulong.loc[:,'specs'].apply(lambda x: x.split(' ')[1]) 
    df_gulong.loc[:,'width'] = df_gulong.loc[:,'specs'].apply(lambda x: cleanup_specs(x, 'width'))
    df_gulong.loc[:,'aspect_ratio'] = df_gulong.loc[:,'specs'].apply(lambda x: cleanup_specs(x, 'aspect_ratio'))
    df_gulong.loc[:,'diameter'] = df_gulong.loc[:,'specs'].apply(lambda x: cleanup_specs(x, 'diameter'))
    df_gulong.loc[:,'correct_specs'] = df_gulong.apply(lambda x: combine_specs(x), axis=1)
    df_gulong.loc[:,'price_gulong'] = df_gulong.loc[:,'price'].apply(lambda x: float((x.split('₱')[1]).replace(',', '')))
    
    # edge cases
    df_gulong.loc[:,'name'] = df_gulong.loc[:,'name'].apply(lambda x: re.sub('TRANSIT.*ARZ.?6-X', 'TRANSITO ARZ6-X', x)
                                                       if re.search('TRANSIT.*ARZ.?6-X', x) else x)
    
    # drop columns
    df_gulong.drop(['price','specs'], 1, inplace=True)
    
    # save file
    if save:
        df_gulong.to_csv("gulong_prices.csv")
        
    return df_gulong

# dictionary of xpath for product info per website
xpath_prod = {'gulong' : {
                 'tires': '//a[@class="flex-1 mb-1 flex items-center min-h-h60p font-semibold text-sm block w-full text-left cursor-pointer capitalize gulong-font"]',
                 'price': '//span[@class="mr-3 font-bold"]',
                 'info' : '//a[@class="flex-1 mb-1 flex items-center min-h-h60p font-semibold text-sm block w-full text-left cursor-pointer capitalize gulong-font"]'},
              'gogulong': {
                'tires': '//div[@class="row subtitle-1 font-weight-bold no-gutters row--dense"]',
                'price': '//span[@class="ele-price-per-tire"]',
                'info': '//div[@class="row subtitle-2 no-gutters row--dense"]'}
         }

if __name__ == '__main__':
    driver_path = os.getcwd() + '\\geckodriver.exe'
    driver = Firefox(executable_path = "/home/appuser/.conda/bin/geckodriver", options=options)
    # gulong scraper
    df_gulong = gulong_scraper(driver, xpath_prod, save=True)
    st.title('Gulong.ph Product Scraper')
    st.dataframe(df_gulong)
    driver.quit()