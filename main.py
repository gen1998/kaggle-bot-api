import os

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from kaggle import KaggleApi

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from datetime import datetime
from time import sleep
import numpy as np
import json

from tqdm import tqdm

def extract_kaggle(kaggleAccounts):
    # selenium driverの定義
    driver_path = '/app/.chromedriver/bin/chromedriver'
    service = Service(executable_path=driver_path)

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--remote-debugging-port=9222')

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(950, 800)

    extract_dict = {}

    for ka in tqdm(kaggleAccounts):
        URL = f"https://www.kaggle.com/{ka}/competitions?tab=active"
        """
        driver.get(URL)

        sleep(3)

        
        html = driver.page_source.encode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        try:
            #soup_find = soup.find_all('ul', class_=lambda value: value and value.startswith('km-list km-list'))[0]
            soup_find = soup.find_all('div', class_=lambda value: value and value.startswith('sc-fVzpDt'))[0]
        except:
            continue
        
        if len(soup_find)<1:
            continue

        competition_name = soup_find.find_all('div', class_=lambda value: value and value.startswith('sc-blmEgr'))
        #competition_rank = soup_find.find_all('span', class_=lambda value: value and value.startswith('sc-hIPBNq'))

        #for name, rank in zip(competition_name, competition_rank):
        for name in competition_name:
            #rank_ = rank.contents[0]
            name_ = name.contents[0]
            #output = f"{int(rank_[:rank_.find('/')])}位@{ka}"
            output = f"@{ka}"
            if name_ in extract_dict.keys():
                extract_dict[name_].append(output)
            else:
                extract_dict[name_] = [output]
        """

        options = webdriver.ChromeOptions()
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        driver = webdriver.Chrome(options=options)

        driver.get(URL)
        sleep(3)

        logs = driver.get_log('performance')

        for entry in logs:
            message_data = json.loads(entry['message'])['message']['params']
            
            # リクエスト情報が存在する場合のみ処理
            if 'request' in message_data:
                request_data = message_data['request']
                request_url = request_data['url']
                if request_url=="https://www.kaggle.com/api/i/search.SearchContentService/ListSearchContent":
                    post_data = request_data['postData']
                    post_data = json.loads(post_data)
                    list_type = post_data['filters']['listType']
                    # activeのみ表示
                    if list_type.find("ACTIVE")>0:
                        requestid = message_data["requestId"]
                        response = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': requestid})
                        break
        
        response = response['body']
        response = json.loads(response)

        if 'documents' in response.keys():
            response = response['documents']
            for res in response:
                if 'teamRank' in res['competitionDocument'].keys():
                    rank = res['competitionDocument']['teamRank']
                    name = res['title']
                    output = f"{int(rank)}位@{ka}"
                else:
                    name = res['title']
                    output = f"順位なし@{ka}"   
            
                if name in extract_dict.keys():
                    extract_dict[name].append(output)
                else:
                    extract_dict[name] = [output]
    
    return extract_dict

def extract_competition():
    # Kaggle APIの定義
    api = KaggleApi()
    api.authenticate()

    competitions_list = api.competitions_list()
    competition_dict = {}

    for com in competitions_list:
        reward = com.reward
        if "$" in reward:
            d = com.deadline - datetime.now()
            competition_dict[com.title] = [com.ref[com.ref.rfind('/')+1:], reward, d.days, com.teamCount, com.url]
    
    return competition_dict

def extract_spreadsheet():
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    # 辞書オブジェクト。認証に必要な情報をHerokuの環境変数から呼び出している
    credential = {
                    "type": "service_account",
                    "project_id": os.environ['SHEET_PROJECT_ID'],
                    "private_key_id": os.environ['SHEET_PRIVATE_KEY_ID'],
                    "private_key": os.environ['SHEET_PRIVATE_KEY'],
                    "client_email": os.environ['SHEET_CLIENT_EMAIL'],
                    "client_id": os.environ['SHEET_CLIENT_ID'],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url":  os.environ['SHEET_CLIENT_X509_CERT_URL']
                }
    
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(credential, scope)
    client = gspread.authorize(credentials)

    #共有設定したスプレッドシートの1枚目のシートを開く
    SpreadSheet = client.open_by_key(os.environ['SPREADSHEET_KEY'])
    RawData = SpreadSheet.worksheet(os.environ['SPREADSHEET_NAME_1'])

    data = RawData.get_all_values()
    name_list = np.array(data)[:, 8][1:]

    return list(name_list)

def main():
    kaggleAccounts = extract_spreadsheet()
    channel = '30_kaggle共有'
    #channel = '91_新運営_random'

    # seleniumによって抽出された結果
    extract_dict = extract_kaggle(kaggleAccounts)
    # kaggleのサイトから最新コンペのリストを取得
    competition_dict = extract_competition()

    # slack api
    slack_token = os.environ['SLACK_TOKEN']
    client = WebClient(token=slack_token)

    text = "現在コンペに参加している人の一覧\n"
    
    competition_dict = {k: v for k, v in sorted(competition_dict.items(), key=lambda x:x[1][2])}

    for k, v in competition_dict.items():
        if k in extract_dict.keys():
            text += f"＊ ＊<{v[4]}|{k}>＊ \n \t(残り{v[2]}日,\t 参加{v[3]}チーム)\n \t\t>>>>\t\t["
            members = extract_dict[k]

            for n in members:
                text += f"{n},  "
            text += "]\n"

    # slackに通知する
    try:
        response = client.chat_postMessage(
            channel=channel,
            text=text
        )
    except SlackApiError as e:
        assert e.response["error"] 
 
if __name__ == '__main__':
    main()