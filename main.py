import os

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from time import sleep

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from kaggle import KaggleApi

from datetime import datetime

def main():
    kaggleAccounts = ["daikon99"]
    channel = '90_新運営'

    driver_path = '/app/.chromedriver/bin/chromedriver'

    options = Options()
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-extensions')
    options.add_argument('--proxy-server="direct://"')
    options.add_argument('--proxy-bypass-list=*')
    options.add_argument('--start-maximized')
    options.add_argument('--headless')

    driver = webdriver.Chrome(executable_path = driver_path, chrome_options = options)

    output = ""
    output_d = {}

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
            if s.contents[0] in output_d.keys():
                output_d[s.contents[0]].append(ka)
            else:
                output_d[s.contents[0]] = [ka]
        txt += "\n"
        output += txt
    
    slack_token = os.environ['SLACK_TOKEN']
    client = WebClient(token=slack_token)

    api = KaggleApi()
    api.authenticate()

    competitions = api.competitions_list()

    competition_d = {}

    for com in competitions:
        reward = com.reward
        if "$" in reward:
            d = com.deadline - datetime.now()
            competition_d[com.title] = [com.ref[com.ref.rfind('/')+1:], reward, d.days, com.teamCount]

    text = "現在コンペに参加している人の一覧\n"
    for k,v in output_d.items():
        if k in competition_d.keys():
            com = competition_d[k]
            text += f"＊ ＊{k}＊ \n \t(残り{com[2]}日,\t 参加{com[3]}チーム)\n \t\t>>>>\t\t["
        
            for n in v:
                text += f"＠{n}, "
            text += "]\n"

    try:
        response = client.chat_postMessage(
            channel=channel,
            text=text
        )
    except SlackApiError as e:
        assert e.response["error"] 
 
if __name__ == '__main__':
    main()