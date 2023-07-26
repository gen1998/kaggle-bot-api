import os

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from time import sleep

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from kaggle import KaggleApi

from datetime import datetime

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

    for ka in kaggleAccounts:
        txt = ""
        URL = f"https://www.kaggle.com/{ka}/competitions?tab=active"
        driver.get(URL)

        sleep(3)

        html = driver.page_source.encode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        sf = soup.find_all('ul', class_=lambda value: value and value.startswith('km-list km-list'))[0]
        sf = sf.find_all('div', class_=lambda value: value and value.startswith('sc-beqWaB'))

        if len(sf)<1:
            continue

        txt = f"{ka} : "
        for s in sf:
            txt += s.contents[0]
            txt += ", "
            if s.contents[0] in extract_dict.keys():
                extract_dict[s.contents[0]].append(ka)
            else:
                extract_dict[s.contents[0]] = [ka]
        txt += "\n"
    
    return extract_dict

def extract_kaggle():
    # Kaggle APIの定義
    api = KaggleApi()
    api.authenticate()

    competitions_list = api.competitions_list()
    competition_dict = {}

    for com in competitions_list:
        reward = com.reward
        if "$" in reward:
            d = com.deadline - datetime.now()
            competition_dict[com.title] = [com.ref[com.ref.rfind('/')+1:], reward, d.days, com.teamCount]
    
    return competition_dict


def main():
    kaggleAccounts = ["daikon99"]
    channel = '90_新運営'

    # seleniumによって抽出された結果
    extract_dict = extract_kaggle(kaggleAccounts)
    # kaggleのサイトから最新コンペのリストを取得
    competition_dict = extract_dict()

    # slack api
    slack_token = os.environ['SLACK_TOKEN']
    client = WebClient(token=slack_token)

    text = "現在コンペに参加している人の一覧\n"
    for k,v in extract_dict.items():
        if k in competition_dict.keys():
            com = competition_dict[k]
            text += f"＊ ＊{k}＊ \n \t(残り{com[2]}日,\t 参加{com[3]}チーム)\n \t\t>>>>\t\t["
        
            for n in v:
                text += f"＠{n}, "
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