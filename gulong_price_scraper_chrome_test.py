# -*- coding: utf-8 -*-
"""
Created on Wed Aug  3 11:32:29 2022

@author: carlo
"""

import sys
import subprocess
import pkg_resources

required = {'pandas', 'numpy', 'selenium', 'datetime', 'streamlit-aggrid'}
installed = {pkg.key for pkg in pkg_resources.working_set}
missing = required - installed

if missing:
    python = sys.executable
    subprocess.check_call([python, '-m', 'pip', 'install', *missing], stdout=subprocess.DEVNULL)

import pandas as pd
import numpy as np
import re, sys
from datetime import datetime

import streamlit as st
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from st_aggrid import GridOptionsBuilder, AgGrid
st.set_page_config(page_icon=":chart_with_upwards_trend:", page_title="Gulong Price Comparison")

# to run selenium in headless mode (no user interface/does not open browser)
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument("--disable-gpu")
options.add_argument("--disable-features=NetworkService")
options.add_argument("--window-size=1920x1080")
options.add_argument("--disable-features=VizDisplayCompositor")


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
    tires_gulong = driver.find_elements(By.XPATH, xpath_info['tires'])
    # prices
    price_gulong = driver.find_elements(By.XPATH, xpath_info['price'])
    # specs
    info_gulong = driver.find_elements(By.XPATH, xpath_info['info'])
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

@st.experimental_memo
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

@st.experimental_memo(suppress_st_warning=True)
def gulong_scraper(_driver, xpath_prod):
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
    last_page = 3
    tire_list, price_list, info_list = [], [], []
    st.write('Loading Gulong.ph products..')
    mybar = st.progress(0)
    # iterate over product pages
    for page in range(last_page):
        url_page = 'https://gulong.ph/shop?page=' + str(page+1)
        driver.get(url_page)
        print("Getting info from Page: {}".format(page+1))
        tire_list_gulong, price_list_gulong, info_list_gulong = scrape_data(driver, 
                        [tire_list, price_list, info_list], xpath_prod['gulong'])
        # update progress bar
        mybar.progress(round((page+1)/last_page, 2))
    # remove progress bar
    mybar.empty()
    # create dataframe
    df_gulong = pd.DataFrame({'name': tire_list_gulong, 'price': price_list_gulong, 'specs': info_list_gulong})
    print ('Collected {} items.'.format(len(df_gulong)))
    # data cleaning and engineering
    df_gulong = df_gulong[df_gulong.loc[:,'specs'] != 'Promo']
    df_gulong.loc[:,'brand'] = df_gulong.loc[:,'specs'].apply(lambda x: x.split(' ')[0]) 
    df_gulong.loc[:,'specs'] = df_gulong.loc[:,'specs'].apply(lambda x: x.split(' ')[1]) 
    df_gulong.loc[:,'width'] = df_gulong.loc[:,'specs'].apply(lambda x: cleanup_specs(x, 'width'))
    df_gulong.loc[:,'aspect_ratio'] = df_gulong.loc[:,'specs'].apply(lambda x: cleanup_specs(x, 'aspect_ratio'))
    df_gulong.loc[:,'diameter'] = df_gulong.loc[:,'specs'].apply(lambda x: cleanup_specs(x, 'diameter'))
    df_gulong.loc[:,'correct_specs'] = df_gulong.apply(lambda x: combine_specs(x), axis=1)
    df_gulong.loc[:,'price_gulong'] = df_gulong.loc[:,'price'].apply(lambda x: round(float((x.split('₱')[1]).replace(',', '')), 2))
    
    # edge cases
    df_gulong.loc[:,'name'] = df_gulong.loc[:,'name'].apply(lambda x: re.sub('TRANSIT.*ARZ.?6-X', 'TRANSITO ARZ6-X', x)
                                                       if re.search('TRANSIT.*ARZ.?6-X', x) else x)
    
    # drop columns
    df_gulong.drop(columns=['price','specs'], inplace=True)  
    return df_gulong

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
    # check if error message for page
    st.write('Scraping competitor prices..')
    mybar2 = st.progress(0)
    specs_err_dict = {}
    for n, spec in enumerate(np.sort(df_gulong.loc[:,'correct_specs'].unique())):
        # obtain specs
        w, ar, d = spec.split('/')
        print ('Specs: ', spec)
        # open web page
        url_page = 'https://gogulong.ph/search-results?width='+ w +'&aspectRatio=' + ar + '&rimDiameter=' + d
        _driver.get(url_page)
        
        err_message = len(_driver.find_elements(By.XPATH, '//div[@class="searchResultEmptyMessage"]'))
        specs_err_dict[spec] = err_message
        print ('Error message: {}'.format(err_message))
        if err_message == 0:
            # check number of items
            _driver.implicitly_wait(5)
            num_items = get_num_items(_driver, '//div[@class="subtitle-2 font-weight-medium px-1 pb-2 grey--text col-md-7 col-12"]//span', site='gogulong')
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
                            page_button = _driver.find_element(By.XPATH, '//li//button[@aria-label="Goto Page {}"]'.format(page+2))
                            _driver.execute_script("arguments[0].click();", page_button)
    
            else:
                tire_list, price_list, info_list = scrape_data(_driver, [tire_list, price_list, info_list], xpath_prod['gogulong'], site='gogulong')
            # update progress bar
        else:
            continue
        mybar2.progress(round((n+1)/df_gulong.loc[:,'correct_specs'].nunique(), 2))
        print ('Collected total {} tire items'.format(len(tire_list)))
    
    try:
        df_gogulong = pd.DataFrame({'name': tire_list, 'price': price_list, 'specs': info_list})
        df_gogulong.loc[:,'width'] = df_gogulong.loc[:,'specs'].apply(lambda x: re.search("(\d{3}/)|(\d{2}[Xx])|(\d{3} )", x)[0][:-1])
        df_gogulong.loc[:,'aspect_ratio'] = df_gogulong.loc[:, 'specs'].apply(lambda x: re.search("(/\d{2})|(X.{4})|( R)", x)[0][1:])
        df_gogulong.loc[:,'diameter'] = df_gogulong.loc[:, 'specs'].apply(lambda x: re.search('R.*\d{2}', x)[0].replace(' ', '')[1:3])
        df_gogulong.loc[:,'ply'] = df_gogulong.loc[:,'specs'].apply(lambda x: re.search('(\d{1}PR)|(\d{2}PR)', x)[0][:-2] if re.search('(\d{1}PR)|(\d{2}PR)', x) else '0')
        df_gogulong.loc[:,'price_gogulong'] = df_gogulong.loc[:,'price'].apply(lambda x: float((x.split(' ')[1]).replace(',', '')))
        df_gogulong.loc[:,'correct_specs'] = df_gogulong.apply(lambda x: combine_specs(x), axis=1)
        df_gogulong.drop(columns=['price','specs'], inplace=True)
    except:
        df_gogulong = pd.DataFrame({'name': tire_list, 'price': price_list, 'specs': info_list})
    # remove progress bar
    mybar2.empty()
    return df_gogulong, specs_err_dict

@st.experimental_memo
def get_intersection(df_gulong, df_gogulong):
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
    left_cols = ['name', 'brand', 'price_gulong', 'correct_specs']
    right_cols = ['name', 'price_gogulong', 'correct_specs', 'ply']
    df_merged = pd.merge(df_gulong[left_cols], df_gogulong[right_cols], how='left', left_on=['name', 'correct_specs'], right_on=['name', 'correct_specs'])
    df_merged = df_merged[['name', 'brand', 'correct_specs', 'price_gulong', 'price_gogulong', 'ply']]
    df_merged = df_merged[df_merged['price_gogulong'].isnull()==False].sort_values('name').reset_index(drop=True)

    return df_merged

#@st.experimental_memo(suppress_st_warning=True)
def show_table(df):
    # table settings

    gb = GridOptionsBuilder.from_dataframe(df.sort_values(by='name'))
    gb.configure_default_column(min_column_width=8)
    gridOptions = gb.build()
    
    # selection settings
    data_selection = AgGrid(
        df.sort_values(by='name'),
        gridOptions=gridOptions,
        data_return_mode='AS_INPUT', 
        update_mode='MODEL_CHANGED', 
        fit_columns_on_grid_load=True,
        theme='blue', #Add theme color to the table
        enable_enterprise_modules=True,
        height=500, 
        reload_data=False)

@st.experimental_memo
def convert_csv(df):
    # IMPORTANT: Cache the conversion to prevent recomputation on every rerun.
    return df.to_csv().encode('utf-8')

@st.experimental_memo
def last_update_date():
    return datetime.today().strftime('%Y-%m-%d')

def update():
    st.experimental_memo.clear()
    st.experimental_rerun()

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
    st.title('Gulong.ph Product Scraper')
    st.markdown('''
                This app collects product info from Gulong.ph and other competitor platforms.
                ''')
    driver = Chrome(options=options)
    # gulong scraper
    df_gulong = gulong_scraper(driver, xpath_prod)
    st.write('Found {} Gulong.ph products.'.format(len(df_gulong)))  
    show_table(df_gulong)

    st.download_button(
        label ="Download",
        data = convert_csv(df_gulong),
        file_name = "gulong_prices.csv",
        key='download-gulong-csv'
        )
    
    driver.implicitly_wait(3)
    #gogulong scraper
    df_gogulong, err_dict = gogulong_scraper(driver, xpath_prod, df_gulong)
    # merge/get intersection of product lists
    df_merged = get_intersection(df_gulong, df_gogulong)
    # close driver
    driver.quit()
    st.markdown('''
                This table shows Gulong.ph products which are also found in competitor platforms.\n
                ''')
    st.write('Found {} common items.'.format(len(df_merged)))
    show_table(df_merged)
    # download csv
    if st.download_button(
        label ="Download",
        data = convert_csv(df_merged),
        file_name = "gulong_prices_compare.csv",
        key='download-merged-csv'):
        st.session_state[last_update_date()] = df_merged
    st.info('Last updated: {}'.format(last_update_date()))
    
    df_file_date = st.selectbox('To download previous versions, select the date and press download.',
                 options = pd.Series(list(st.session_state.keys())),
                 index = 0)
    st.download_button(
        label ="Download",
        data = convert_csv(st.session_state[df_file_date]),
        file_name = "gulong_prices_compare_" + df_file_date + ".csv",
        key='download-prev-csv'
        )
    
    st.warning('''
                If you need to update the lists, the button below will clear the cache and rerun the app.
                ''')
    if st.button('Update'):
        update()
    
    # 
    