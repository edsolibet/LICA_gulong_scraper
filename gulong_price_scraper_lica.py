# -*- coding: utf-8 -*-
"""
Created on Wed Aug  3 11:32:29 2022

@author: carlo
"""

import pandas as pd
import numpy as np
from decimal import Decimal
import re, time
import datetime as dt
from datetime import datetime 
from pytz import timezone
import gspread

import streamlit as st
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from st_aggrid import GridOptionsBuilder, AgGrid
from functools import reduce
import warnings

# to run selenium in headless mode (no user interface/does not open browser)
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("--disable-gpu")
options.add_argument("--disable-features=NetworkService")
options.add_argument("--window-size=1920x1080")
options.add_argument("--disable-features=VizDisplayCompositor")

# set timezone
phtime = timezone('Asia/Manila')

def get_num_items(driver, xpath):
    '''
    Used by gogulong_scraper
    
    For future reference:
        Test usage of driver.wait
    
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
    total_items : int
        total number of products available for scraping
    '''
    
    try: 
        elements_present = WebDriverWait(driver, 3) \
                .until(EC.presence_of_element_located((By.XPATH, xpath)))
        if elements_present:
            total_items_text = driver.find_elements(By.XPATH, xpath)
            total_items_list = [items.text for items in total_items_text]
            total_items = [item for item in total_items_list[0].split(' ') 
                           if item.isdigit()][0]
    except:
        total_items = 0
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
    tires_gulong = driver.find_elements(By.XPATH, xpath_info['tires'])
    # prices
    price_gulong = driver.find_elements(By.XPATH, xpath_info['price'])
    # specs
    info_gulong = driver.find_elements(By.XPATH, xpath_info['info'])
    # save scraped text
    for i in range(len(price_gulong)):
        try:
            if price_gulong[i].text == '':
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
        except:
            break
    return [tire_list_gulong, price_list_gulong, info_list_gulong]

@st.experimental_memo
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
    error_aspect_ratio = {'0.': '10.5',
                          '2.': '12.5',
                          '3.': '13.5',
                          '5.': '15.5'}
    
    specs_len = len(specs.split('/'))
    if specs_len == 1:
        return specs.split('/')[0]
    else:
        if col == 'width':
            return specs.split('/')[0][-3:].split('X')[0]
        elif col == 'aspect_ratio':
            if 'X' in specs:
                return specs.split('X')[1].split('/')[0]
            else:
                if specs.split('/')[1] == '0' or specs.split('/')[1] == '':
                    return 'R'
                elif specs.split('/')[1] in error_aspect_ratio.keys():
                    return error_aspect_ratio[specs.split('/')[1]]
                else:
                    return specs.split('/')[1]
        elif col == 'diameter':
            return specs.split('/')[2][1:3]
        else:
            return specs

#@st.experimental_memo
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
    if '.' in str(row['aspect_ratio']):
        return '/'.join([str(row['width']), str(float(row['aspect_ratio'])), str(row['diameter'])])
    else:
        return '/'.join([str(row['width']), str(row['aspect_ratio']), str(row['diameter'])])


def fix_diameter(d):
    '''
    Fix diameter values
    
    Parameters
    ----------
    d: string
        diameter values in string format
        
    Returns:
    --------
    d: string
        fixed diameter values
    
    '''
    if len(d.split('R')) == 1:
        if len(d.split('R')[0].split('C')) == 1:
            return str(d)
        else:
            return d.split('R')[0].split('C')[0]
    else:
        return d.split('R')[1].split('C')[0]

            
def fix_names(sku_name, name = None, comp=None):
    '''
    Fix product names to match competitor names
    
    Parameters
    ----------
    sku_name: str
        input SKU name string
    name : str (optional)
        optional given model name
    comp: list
        optional list of model names to compare with
    
    Returns
    -------
    name: str
        fixed names as UPPERCASE
    '''
    
    # replacement should be all caps
    change_name_dict = {'TRANSIT.*ARZ.?6-X' : 'TRANSITO ARZ6-X',
                        'TRANSIT.*ARZ.?6-A' : 'TRANSITO ARZ6-A',
                        'TRANSIT.*ARZ.?6-M' : 'TRANSITO ARZ6-M',
                        'OPA25': 'OPEN COUNTRY A25',
                        'OPA28': 'OPEN COUNTRY A28',
                        'OPA32': 'OPEN COUNTRY A32',
                        'OPA33': 'OPEN COUNTRY A33',
                        'OPAT\+': 'OPEN COUNTRY AT PLUS', 
                        'OPAT2': 'OPEN COUNTRY AT 2',
                        'OPMT2': 'OPEN COUNTRY MT 2',
                        'OPAT OPMT': 'OPEN COUNTRY AT',
                        'OPAT': 'OPEN COUNTRY AT',
                        'OPMT': 'OPEN COUNTRY MT',
                        'OPRT': 'OPEN COUNTRY RT',
                        'OPUT': 'OPEN COUNTRY UT',
                        'DC -80': 'DC-80',
                        'DC -80+': 'DC-80+',
                        'KM3': 'MUD-TERRAIN T/A KM3',
                        'KO2': 'ALL-TERRAIN T/A KO2',
                        'TRAIL-TERRAIN T/A' : 'TRAIL-TERRAIN',
                        '265/70/R16 GEOLANDAR 112S': 'GEOLANDAR A/T G015',
                        '265/65/R17 GEOLANDAR 112S' : 'GEOLANDAR A/T G015',
                        '265/65/R17 GEOLANDAR 112H' : 'GEOLANDAR G902',
                        'GEOLANDAR A/T 102S': 'GEOLANDAR A/T-S G012',
                        'GEOLANDAR A/T': 'GEOLANDAR A/T G015',
                        'ASSURACE MAXGUARD SUV': 'ASSURANCE MAXGUARD SUV',
                        'EFFICIENTGRIP SUV': 'EFFICIENTGRIP SUV',
                        'EFFICIENGRIP PERFORMANCE SUV':'EFFICIENTGRIP PERFORMANCE SUV',
                        'WRANGLE DURATRAC': 'WRANGLER DURATRAC',
                        'WRANGLE AT ADVENTURE': 'WRANGLER AT ADVENTURE',
                        'WRANGLER AT ADVENTURE': 'WRANGLER AT ADVENTURE',
                        'WRANGLER AT SILENT TRAC': 'WRANGLER AT SILENTTRAC',
                        'ENASAVE  EC300+': 'ENSAVE EC300 PLUS',
                        'SAHARA AT2' : 'SAHARA AT 2',
                        'SAHARA MT2' : 'SAHARA MT 2',
                        'WRANGLER AT SILENT TRAC': 'WRANGLER AT SILENTTRAC',
                        'POTENZA RE003 ADREANALIN': 'POTENZA RE003 ADRENALIN',
                        'POTENZA RE004': 'POTENZA RE004',
                        'SPORT MAXX 050' : 'SPORT MAXX 050',
                        'DUELER H/T 470': 'DUELER H/T 470',
                        'DUELER H/T 687': 'DUELER H/T 687 RBT',
                        'DUELER A/T 697': 'DUELER A/T 697',
                        'DUELER A/T 693': 'DUELER A/T 693 RBT',
                        'DUELER H/T 840' : 'DUELER H/T 840 RBT',
                        'EVOLUTION MT': 'EVOLUTION M/T',
                        'BLUEARTH AE61' : 'BLUEARTH XT AE61',
                        'BLUEARTH ES32' : 'BLUEARTH ES ES32',
                        'BLUEARTH AE51': 'BLUEARTH GT AE51',
                        'COOPER STT PRO': 'STT PRO',
                        'COOPER AT3 LT' : 'AT3 LT',
                        'COOPER AT3 XLT' : 'AT3 XLT',
                        'A/T3' : 'AT3',
                        'ENERGY XM+' : 'ENERGY XM2+',
                        'XM2+' : 'ENERGY XM2+',
                        'AT3 XLT': 'AT3 XLT',
                        }
    
    # uppercase and remove double spaces
    raw_name = re.sub('  ', ' ', sku_name).upper().strip()
    # specific cases
    for key in change_name_dict.keys():
        if re.search(key, raw_name):
            return change_name_dict[key]
        else:
            continue
    
    # if match list provided
    
    if comp is not None:
        # check if any name from list matches anything in sku name
        match_list = [n for n in comp if re.search(n, raw_name)]
        # exact match from list
        if len(match_list) == 1:
            return match_list[0]
        # multiple matches (i.e. contains name but with extensions)
        elif len(match_list) > 1:
            long_match = ''
            for m in match_list:
                if len(m) > len(long_match):
                    long_match = m
            return long_match
        # no match
        else:
            if name is not None:
                return re.sub('  ', ' ', name).upper().strip()
            else:
                return raw_name
    else:
        if name is not None:
            return re.sub('  ', ' ', name).upper().strip()
        else:
            return raw_name
    

def remove_exponent(num):
    '''
    Removes unnecessary zeros from decimals

    Parameters
    ----------
    num : Decimal(number)
        number applied with Decimal function (see import decimal from Decimal)

    Returns
    -------
    number: Decimal
        Fixed number in Decimal form

    '''
    return num.to_integral() if num == num.to_integral() else num.normalize()

def fix_aspect_ratio(ar):
    '''
    Fix raw aspect ratio data
    
    Parameters
    ----------
    ar: float or string
        input raw aspect ratio data
        
    Returns
    -------
    ar: string
        fixed aspect ratio data in string format for combine_specs
    
    '''
    error_aspect_ratio = {'.5' : '9.5',
                          '0.': '10.5',
                          '2.': '12.5',
                          '3.': '13.5',
                          '5.': '15.5'}
    
    if str(ar) == '0' or str(ar) == 'R1':
        return 'R'
    elif np.isnan(float(ar)):
        return 'R'
    elif str(float(ar)).isnumeric():
        return str(ar)
    elif str(ar) in error_aspect_ratio.keys():
        return error_aspect_ratio[str(ar)]
    else:
        return str(remove_exponent(Decimal(str(ar))))

def raw_specs(x):
    if str(x['aspect_ratio']) == 'nan' or x['aspect_ratio'] == 0:
        return '/'.join([str(x['width']), str(x['diameter'])+'C'])
    else:
        return '/'.join([str(x['width']), str(x['aspect_ratio']), str(x['diameter'])])

@st.experimental_memo(suppress_st_warning=True)
def get_gulong_data():
    '''
    Get gulong.ph data from backend
    
    Returns
    -------
    df : dataframe
        Gulong.ph product info dataframe
    '''
    df = pd.read_csv('http://app.redash.licagroup.ph/api/queries/130/results.csv?api_key=JFYeyFN7WwoJbUqf8eyS0388PFE7AiG1JWa6y9Zp')
    df = df[df.is_model_active==1].rename(columns={'model': 'sku_name',
                                                   'pattern' : 'name',
                                                   'make' : 'brand',
                                                   'section_width':'width', 
                                                   'rim_size':'diameter', 
                                                   'price' : 'price_gulong'}).reset_index()
    
    df.loc[:, 'raw_specs'] = df.apply(lambda x: raw_specs(x), axis=1)
    df.loc[:, 'width'] = df.apply(lambda x: str(x['width']).split('X')[0], axis=1)
    df.loc[:, 'aspect_ratio'] = df.apply(lambda x: fix_aspect_ratio(x['aspect_ratio']), axis=1)
    
    df.loc[:, 'diameter'] = df.apply(lambda x: fix_diameter(x['diameter']), axis=1)
    df.loc[:, 'correct_specs'] = df.apply(lambda x: combine_specs(x), axis=1)
    df.loc[:, 'name'] = df.apply(lambda x: fix_names(x['name']), axis=1)
    df = df[df.name !='-']
    return df[['sku_name', 'raw_specs', 'price_gulong', 'name', 'brand', 'width', 'aspect_ratio', 'diameter', 'vehicle_type', 'correct_specs']]

@st.experimental_memo(suppress_st_warning=True)
def gogulong_scraper(_driver, xpath_prod, df_gulong):
    '''
    Gogulong price scraper
    
    Parameters
    ----------
    driver : selenium
        Chrome driver
    xpath_prod : dictionary
        Dictionary of tires, price, info html xpaths separated by website
    df_gulong: dataframe
        Dataframe of scraped data from gulong
    save : bool, optional
        True if save result to csv. The default is True.

    Returns
    -------
    df_gogulong : dataframe
        Dataframe containing scraped info
    '''
    
    print ('Starting scraping for GoGulong.ph')
    tire_list, price_list, info_list = [], [], []
    mybar2 = st.progress(0)
    specs_err_dict = {}
    # filter out unnecessary specs
    correct_specs = [cs for cs in np.sort(df_gulong.loc[:, 'correct_specs'].unique()) if float(cs.split('/')[0]) > 27]
    # iterate over all viable specs
    for n, spec in enumerate(correct_specs):
        
        # obtain specs
        w, ar, d = spec.split('/')
        print ('Specs: ', spec)
        
        # open web page
        url_page = 'https://gogulong.ph/search-results?width='+ w +'&aspectRatio=' + ar + '&rimDiameter=' + d
        driver.get(url_page)
        
        # check if error message for page
        err_message = len(driver.find_elements(By.XPATH, '//div[@class="searchResultEmptyMessage"]'))
        specs_err_dict[spec] = err_message
        print ('Error message: {}'.format(err_message))
       
        if err_message == 0:
            driver.implicitly_wait(2)
            # check number of items
            num_items = get_num_items(driver, '//div[@class="subtitle-2 font-weight-medium px-1 pb-2 grey--text col-md-7 col-12"]//span')
            # page format changes depending on the number of products included
            print ('{} items on this page: '.format(num_items))
            if int(num_items) >= 5:
                # Show all button
                parent_button_xpath = '//div[@class="subtitle-1 accent--text font-weight-bold pb-2 text-center text-decoration-underline col col-12"]'
                child_button_xpath = '//span[@class="v-btn__content"]'
                see_all_button = driver.find_element(By.XPATH, parent_button_xpath + child_button_xpath)
                driver.execute_script("arguments[0].click();", see_all_button)
    
                # iterate on pages
                for page in range(int(np.ceil(int(num_items)/12))):
                    print("Getting info from Page: {}".format(page+1))
                    tire_list, price_list, info_list = scrape_data(driver, [tire_list, price_list, info_list], xpath_prod['gogulong'], site='gogulong')
                    # go to next page if available
                    if page < (int(np.ceil(int(num_items)/12))-1):
                            page_button = driver.find_element(By.XPATH, '//li//button[@aria-label="Goto Page {}"]'.format(page+2))
                            driver.execute_script("arguments[0].click();", page_button)
    
            else:
                tire_list, price_list, info_list = scrape_data(driver, [tire_list, price_list, info_list], xpath_prod['gogulong'], site='gogulong')
            # update progress bar
        else:
            continue
        mybar2.progress(round((n+1)/df_gulong.loc[:,'correct_specs'].nunique(), 2))
        print ('Collected total {} tire items'.format(len(tire_list)))
    
    # remove progress bar
    mybar2.empty()
    
    # construct dataframe
    # if error, return basic dataframe
    try:
        df_gogulong = pd.DataFrame({'sku_name': tire_list, 'price': price_list, 'specs': info_list})
        df_gogulong.loc[:, 'name'] = df_gogulong.apply(lambda x: fix_names(x.sku_name, comp = df_gulong.name.unique()), axis=1)
        df_gogulong.loc[:,'width'] = df_gogulong.loc[:,'specs'].apply(lambda x: re.search("(\d{3}/)|(\d{2}[Xx])|(\d{3} )", x)[0][:-1])
        df_gogulong.loc[:,'aspect_ratio'] = df_gogulong.loc[:, 'specs'].apply(lambda x: re.search("(/\d{2})|(X.{4})|( R)", x)[0][1:])
        df_gogulong.loc[:,'diameter'] = df_gogulong.loc[:, 'specs'].apply(lambda x: re.search('R.*\d{2}', x)[0].replace(' ', '')[1:3])
        df_gogulong.loc[:,'ply'] = df_gogulong.loc[:,'specs'].apply(lambda x: re.search('(\d{1}PR)|(\d{2}PR)', x)[0][:-2] if re.search('(\d{1}PR)|(\d{2}PR)', x) else '0')
        df_gogulong.loc[:,'price_gogulong'] = df_gogulong.loc[:,'price'].apply(lambda x: float((x.split(' ')[1]).replace(',', '')))
        df_gogulong.loc[:,'correct_specs'] = df_gogulong.apply(lambda x: combine_specs(x), axis=1)
        df_gogulong.drop(columns=['price','specs'], inplace=True)
    except:
        df_gogulong = pd.DataFrame({'name': tire_list, 'price': price_list, 'specs': info_list})
        warnings.warn('Error encounted in Gogulong dataframe processing.')
    return df_gogulong, specs_err_dict

def get_tire_info(row):
    '''
    Helper function to extract tire information 
    terrain, on_stock, year
    '''
    
    info = row.split('\n')
    if len(info) == 3:
        terrain = info[0]
        on_stock = info[1]
        year = info[2]
    elif len(info) == 2:
        terrain = info[0]
        if info[1] in ['On Stock', 'Pre-Order']:            
            on_stock = info[1]
            year = float(np.NaN)
        else:
            on_stock = float(np.NaN)
            year = info[1]
    elif len(info) == 1:
        terrain = float(np.NaN)
        year = float(np.NaN)
        if info[0] in ['On Stock', 'Pre-Order']:
            on_stock = info[0]
        else:
            on_stock = float(np.NaN)
    return terrain, on_stock, year

def cleanup_price(price):
    '''
    Helper function to extract price from tiremanila
    '''
    return round(float(''.join(price[1:].split(','))), 2)

def get_specs(raw_specs):
    '''
    Helper function to extract dimensions from raw specs of tiremanila products
    '''
    
    diam_slice = raw_specs.split('R')
    diameter = diam_slice[1]
    if '/' in diam_slice[0]:
        temp = diam_slice[0].split('/')
        return temp[0], temp[1], diameter
    elif 'X' in diam_slice[0]:
        temp = diam_slice[0].split('X')
        return temp[0], temp[1], diameter
    else:
        return diam_slice[0], 'R', diameter

def get_brand_model(sku_name):
    '''
    Helper function to extract brand and model from tiremanila products
    '''
    sku_minus_specs = sku_name.upper().split(' ')[1:]
    if '(' in sku_minus_specs[0]:
        sku_minus_specs = sku_minus_specs[1:]
    
    brand_dict = {'BFG': 'BFGOODRICH',
                  'DOUBLE COIN' : 'DOUBLECOIN'}
    
    sku_minus_specs = ' '.join(sku_minus_specs)
    for key in brand_dict.keys():
        if re.search(key, sku_minus_specs):
            sku_minus_specs = re.sub(key, brand_dict[key], sku_minus_specs)
        else:
            continue
    
    sku_minus_specs = sku_minus_specs.split(' ')
    brand = sku_minus_specs[0]
    model = ' '.join(sku_minus_specs[1:]).strip()
    return brand, model

def scrape_info(driver, info_list):
    # index_list, style_list, qty_list = info_list
    info = driver.find_elements(By.XPATH, '//div[@class="sv-tile__table sv-no-border"]')
    for j in info:
        split_info = j.text.split('\n')
        for index, i in enumerate(['Index:', 'Style:', 'Qty:']):
            if i in split_info:
                info_list[index].append(split_info[split_info.index(i)+1])
            else:
                info_list[index].append(str(np.NaN))
    return info_list
        

@st.experimental_memo(suppress_st_warning=True)
def tiremanila_scraper(_driver, xpath_prod, df_gulong):
    '''
    TireManila price scraper
    
    Parameters
    ----------
    driver : selenium
        Chrome driver
    xpath_prod : dictionary
        Dictionary of tires, price, info html xpaths separated by website

    Returns
    -------
    df_tiremanila : dataframe
        Dataframe containing scraped info
    '''
    
    print ('Starting scraping for Tiremanila')
    url_page = 'https://tiremanila.com/?page=1'
    driver.get(url_page)
    driver.implicitly_wait(2)
    pages = driver.find_elements(By.XPATH, '//a[@tabindex="0"]')
    
    try: 
        last_page = max([int(page.text) for page in pages if page.text.isnumeric()])
    except:
        last_page = 102
        
    tire_list, price_list, info_list = list(), list(), list()
    index_list, style_list, qty_list = list(), list(), list()
    mybar = st.progress(0)
    for page in range(last_page):
        url_page = 'https://tiremanila.com/?page=' + str(page+1)
        driver.get(url_page)
        print("Getting info from Page: {}".format(page+1))
        tire_list, price_list, info_list = scrape_data(driver, 
                            [tire_list, price_list, info_list], xpath_prod['tiremanila'], 
                            site='tiremanila')
        index_list, style_list, qty_list = scrape_info(driver, [index_list, style_list, qty_list])
        if len(tire_list) != len(qty_list):
            warnings.warn('Information list lengths do not match at page {}'.format(page+1))
        mybar.progress(round((page+1)/last_page, 2))
    mybar.empty()
    
    try:
        df_tiremanila = pd.DataFrame({'sku_name': tire_list, 'price': price_list, 'info': info_list,
                                      'qty_tiremanila': qty_list[:len(tire_list)]})
        df_tiremanila = df_tiremanila[df_tiremanila.sku_name != '']
        df_tiremanila['terrain'], df_tiremanila['on_stock'], df_tiremanila['year'] = zip(*df_tiremanila['info'].map(get_tire_info))
        df_tiremanila.loc[:, 'price_tiremanila'] = df_tiremanila.apply(lambda x: cleanup_price(x['price']), axis=1)
        df_tiremanila.loc[:, 'raw_specs'] = df_tiremanila.apply(lambda x: x['sku_name'].split(' ')[0], axis=1)
        df_tiremanila['width'], df_tiremanila['aspect_ratio'], df_tiremanila['diameter'] = zip(*df_tiremanila.loc[:, 'raw_specs'].map(get_specs))
        df_tiremanila['brand'], df_tiremanila['model'] = zip(*df_tiremanila.loc[:, 'sku_name'].map(get_brand_model))
        df_tiremanila.loc[:,'name'] = df_tiremanila.apply(lambda x: fix_names(x['model'], comp = df_gulong.name.unique()), axis=1)
        df_tiremanila.loc[:, 'correct_specs'] = df_tiremanila.apply(lambda x: combine_specs(x), axis=1)
        df_tiremanila.drop(labels='info', axis=1, inplace=True)
        return df_tiremanila[['sku_name', 'name', 'model', 'brand', 'price_tiremanila', 'qty_tiremanila', 'correct_specs']]
    
    except:
        df_tiremanila = pd.DataFrame({'sku_name': tire_list, 'price': price_list, 'info': info_list,
                                      'qty_tiremanila': qty_list[:len(tire_list)]})
        return df_tiremanila

    

@st.experimental_memo
def get_intersection(df_gulong, df_gogulong, df_tiremanila):
    '''
    Parameters
    ----------
    
    df_gulong : dataframe
        Scraped gulong.ph data
    df_gogulong : dataframe
        Scraped gogulong.ph data
    save : bool
        Save file to csv. The default is True.
    
    Returns
    -------
    '''
    
    # create helper column for duplicated keys
    df_gulong['name_count'] = df_gulong.groupby(['name', 'correct_specs']).cumcount()
    df_gogulong['name_count'] = df_gogulong.groupby(['name', 'correct_specs']).cumcount()
    df_tiremanila['name_count'] = df_tiremanila.groupby(['name', 'correct_specs']).cumcount()
    # select columns to show
    gulong_cols = ['sku_name', 'name', 'name_count', 'brand', 'price_gulong', 'raw_specs', 'correct_specs']
    gogulong_cols = ['name', 'name_count', 'price_gogulong', 'correct_specs']
    tiremanila_cols = ['sku_name', 'name', 'name_count', 'brand', 'price_tiremanila', 'qty_tiremanila', 'correct_specs']
    # merge
    dfs = [df_gulong[gulong_cols], df_gogulong[gogulong_cols], df_tiremanila[tiremanila_cols]]
    df_merged = reduce(lambda left,right: pd.merge(left, right, how='left', on=['name', 'name_count', 'correct_specs']), dfs)
    df_merged_ = df_merged[(df_merged.price_gogulong.notnull()) | (df_merged.price_tiremanila.notnull())]
    df_merged_ = df_merged_[['sku_name_x', 'raw_specs', 'price_gulong', 'price_gogulong', 'price_tiremanila', 'qty_tiremanila', 'brand_x', 'name']]
    df_merged_ = df_merged_.rename(columns={'sku_name_x':'sku_name',
                                            'brand_x': 'brand'})
    # get items unique to tiremanila
    df_tm_only = pd.merge(df_gulong[gulong_cols], df_tiremanila[tiremanila_cols], 
                                    how='outer', on=['name', 'correct_specs'], indicator=True)
    df_tm_only_ = df_tm_only[df_tm_only['_merge'] == 'right_only'][['sku_name_y', 
                                        'name', 'brand_y', 'price_tiremanila', 
                                        'qty_tiremanila', 'correct_specs']]
    df_tm_only_ = df_tm_only_.rename(columns={'sku_name_y':'sku_name',
                                              'brand_y': 'brand'})
    return df_merged_, df_tm_only_


def show_table(df):
    # table settings

    gb = GridOptionsBuilder.from_dataframe(df.sort_values(by='sku_name'))
    gb.configure_default_column(min_column_width=4)
    gridOptions = gb.build()
    
    # selection settings
    AgGrid(
        df.sort_values(by='sku_name'),
        gridOptions=gridOptions,
        data_return_mode='AS_INPUT', 
        update_mode='MODEL_CHANGED',
        autoSizeColumn = 'sku_name',
        fit_columns_on_grid_load=False,
        enable_enterprise_modules=True,
        height=400, 
        reload_data=False)

@st.experimental_memo
def write_to_gsheet(df):
    '''
    Creates new sheet in designated googlesheet and writes selected data from df
    
    Parameters
    ----------
    df: dataframe
        dataframe to write to google sheet
    
    '''
    credentials = {
      "type": "service_account",
      "project_id": "xenon-point-351408",
      "private_key_id": "f19cf14da43b38064c5d74ba53e2c652dba8cbfd",
      "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC5fe2N4yS74jTP\njiyv1EYA+XgnrTkZHwMx4ZY+zLuxx/ODPGxJ3m2e6QRUtz6yBUp1DD3nvzaMYY2d\nea6ti0fO2EPmmNIAZzgWVMOqaGePfXZPN1YN5ncLegZFheZuDrsz0/E+KCVUpLbr\nWBRTBF7l0sZ7paXZsVYOu/QAJI1jPRNF3lFUxMDSE8eGx+/oUmomtl+NfCi/FEJ5\nFCU4pF1FQNmVo885HGe9Tx7UywgaXRvAGJZlA4WVie4d5Jhj8LjZRhSH8+uDgdGX\ngc/4GI8U831oQ2lHsrtYIHHNzs1EG/8Ju+INdgR/Zc5SxNx/BSF8gV7kSueEd8+/\nXlobf5JZAgMBAAECggEAHRPWBOuKCx/jOnQloiyLCsUQplubu0nmxM+Br3eFptFa\n5YQ3z36cPZB2mtcc72gv61hPbgBGC0yRmBGGpfLS/2RchI4JQYHsw2dnQtPaBB7d\nSH66sTQjDjwDNqvOWwtZIj9DroQ5keK+P/dPPFJPlARuE9z8Ojt365hgIBOazGb2\ngIh9wLXrVq7Ki8OXI+/McrxkH3tDksVH2LmzKGtWBA56MRY0v9vnJFjVd+l8Q+05\nIw4lQXt55dK7EmRLIfLnawHYIvnpalCWPe6uAmCTeoOuGASLFJJR2uzcOW9IxM0a\nMkR2dduu5vQl/ahJwxZ2cH40QJUdy7ECQg5QG4qL1wKBgQDugyaPEdoUCGC6MUas\nFR4kwDIkHj/UkgzYtsemmGG0rXCqVtIerPd6FvtKlN8BDzQbyqCaw/pDUqjFoGXN\nW969vkN5Uj9YaQ5qV8c9WLbCcMw9gT6rvqyC8b8FgwaWMKHx7TgI/8xXQ666XqpT\nMTAfINWWei0e/Scqqu6hw0v+UwKBgQDHF5ce9y9mHdVb8B7m0Oz4QIHksktKfoQa\nLoGS601zK6Rr6GeEHb03s4KLG5q9L/o9HUTXqyKERnofdEdfsGsnrKbz2Wsnr8Mk\nGwnNcPTvI3uYkeTBS4paNUxZyGVbxDOrRbBYukgwacaUIGbZ5+we1BxlVN04+l5W\nvAlNEvlfIwKBgBWMcdJhOYOv0hVgWFM5wTRuzNjohrnMzC5ULSuG/uTU+qXZHDi7\nRcyZAPEXDCLLXdjY8LOq2xR0Bl18hVYNY81ewDfYz3JMY4oGDjEjr7dXe4xe/euE\nWY+nCawUz2aIVElINlTRz4Ne0Q1zeg30FrXpQILM3QC8vGolcVPaEiaTAoGBALj7\nNjJTQPsEZSUTKeMT49mVNhsjfcktW9hntYSolEGaHx8TxHqAlzqV04kkkNWPKlZ2\nR2yLWXrFcNqg02AZLraiOE0BigpJyGpXpPf5J9q5gTD0/TKL2XSPaO1SwLpOxiMw\nkPUfv8sbvKIMqQN19XF/axLLkvBJ0DWOaKXwJzs5AoGAbO2BfPYQke9K1UhvX4Y5\nbpj6gMzaz/aeWKoC1KHijEZrY3P58I1Tt1JtZUAR+TtjpIiDY5D2etVLaLeL0K0p\nrti40epyx1RGo76MI01w+rgeZ95rmkUb9BJ3bG5WBrbrvMIHPnU+q6XOqrBij3pF\nWQAQ7pYkm/VubZlsFDMvMuA=\n-----END PRIVATE KEY-----\n",
      "client_email": "googlesheetsarvin@xenon-point-351408.iam.gserviceaccount.com",
      "client_id": "108653350174528163497",
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/googlesheetsarvin%40xenon-point-351408.iam.gserviceaccount.com"
    }
    
    gsheet_key = "12jCVn8EQyxXC3UuQyiRjeKsA88YsFUuVUD3_5PILA2c"
    gc = gspread.service_account_from_dict(credentials)
    sh = gc.open_by_key(gsheet_key)
    
    new_sheet_name = datetime.strftime(phtime.localize(datetime.today()),"%B_%d")
    r,c = df.shape
    
    try:
        sh.add_worksheet(title=new_sheet_name,rows = r+1, cols = c+1)
        worksheet = sh.worksheet(new_sheet_name)
    except:
        worksheet = sh.worksheet(new_sheet_name)
        worksheet.clear()
    worksheet.update([df.columns.tolist()]+df.values.tolist())

@st.experimental_memo
def convert_csv(df):
    # IMPORTANT: Cache the conversion to prevent recomputation on every rerun.
    return df.to_csv().encode('utf-8')

def last_update_date():
    return phtime.localize(datetime.today()).strftime('%Y-%m-%d')

def update():
    st.experimental_memo.clear()
    st.experimental_rerun()

# dictionary of xpath for product info per website
xpath_prod = {'gogulong': {
                'tires': '//div[@class="row subtitle-1 font-weight-bold no-gutters row--dense"]',
                'price': '//span[@class="ele-price-per-tire"]',
                'info': '//div[@class="row subtitle-2 no-gutters row--dense"]'},
              'tiremanila': {
                  'tires': '//h3[@class="sv-tile__title sv-text-reset sv-link-reset"]',
                  'price': '//p[@class="sv-tile__price sv-text-reset"]',
                  'info': '//div[@class="sv-badge-list"]'}
              }

if __name__ == '__main__':
    st.title('Gulong.ph Competitor Product Scraper')
    st.markdown('''
                This app collects product info from Gulong.ph and other competitor platforms.
                ''')
    while True:
        
        df_gulong = get_gulong_data()
        show_table(df_gulong)
        st.write('Found {} Gulong.ph products.'.format(len(df_gulong))) 
        
        # download gulong table
        st.download_button(
            label ="Download Gulong Data",
            data = convert_csv(df_gulong),
            file_name = "gulong_prices.csv",
            key='download-gulong-csv'
            )
        
        col1, col2 = st.columns(2)
        driver = Chrome(options=options)
        # #gogulong scraper
        df_gogulong, err_dict = gogulong_scraper(driver, xpath_prod, df_gulong)
        # merge/get intersection of product lists
        df_tiremanila= tiremanila_scraper(driver, xpath_prod, df_gulong)
        
        with col1:
            st.download_button(
                label ="Download GoGulong data",
                data = convert_csv(df_gogulong),
                file_name = "gogulong_prices.csv",
                key='download-gogulong-csv'
                )
        with col2:
            st.download_button(
                label ="Download TireManila data",
                data = convert_csv(df_tiremanila),
                file_name = "tiremanila_prices.csv",
                key='download-tiremanila-csv'
                )
        
        df_merged, df_tm_only = get_intersection(df_gulong, df_gogulong, df_tiremanila)
        #close driver
        driver.quit()
        
        st.markdown('''
                    This table shows Gulong.ph products which are also found in competitor platforms.\n
                    ''')
        show_table(df_merged)
        
        st.write('Found {} common items.'.format(len(df_merged)))
        
        col3, col4 = st.columns(2)
        with col3:
            # download csv
            st.download_button(label ="Download product comparison", 
                               data = convert_csv(df_merged), 
                               file_name = "gulong_prices_compare.csv", 
                               key='download-merged-csv')
        with col4:
            # download csv
            st.download_button(label ="Download unique tiremanila items", 
                               data = convert_csv(df_tm_only), 
                               file_name = "tiremanila_only.csv", 
                               key='download-tm-csv')
        

        # initialize session_state.last_update dictionary
        if 'last_update' not in st.session_state:
            st.session_state['last_update'] = {phtime.localize(datetime.today()).strftime('%Y-%m-%d') : df_merged}
        
        st.info('Last   updated: {}'.format(sorted(st.session_state.last_update.keys())[-1]))
    
        # st.session_state
        df_file_date = st.selectbox('To download previous versions, select the date and press download.',
                      options = np.asarray(sorted(st.session_state.last_update.keys())),
                      key='last_update_date_select')
        
        st.download_button(
            label ="Download Price Comparison",
            data = convert_csv(st.session_state.last_update[df_file_date]),
            file_name = "gulong_prices_compare_" + df_file_date + ".csv",
            key='download-prev-csv'
            )
        
        # write to gsheet
        write_to_gsheet(df_merged.fillna(''))
        
        st.warning('''
                    If you need to update the lists, the button below will clear the
                    cache and rerun the app.
                    ''')
        
        if st.button('Update'):
            st.session_state.last_update[last_update_date()] = df_merged
            update()
        
        # refresh every hour
        time.sleep(3600)
        t = st.sidebar.time_input('Set app to update at: ', dt.time(3,0, tzinfo=phtime))
        time_now = phtime.localize(datetime.now())
        
        if time_now.hour == t.hour:
            st.session_state.last_update[last_update_date()] = df_merged
            update()
        