import requests
import re
import json
import os
import urllib
import urllib.request
import time
import unicodedata
from bs4 import BeautifulSoup
from requests_html import HTMLSession
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver import Chrome
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from json import dump
ua = UserAgent(path='./fake.useragent.json')
headers = {"User-Agent":ua.random}
# headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
query_url = "https://www.youtube.com/results?search_query="
video_count = 0


def urlsOfVideo(kw): #first, find all urls to the videos and save them in a text file
    file = open('urls.text','a')
    # set headless
    opts = Options()
    opts.add_argument('--headless')
    driver = webdriver.Chrome(options=opts)
    # start scrapping
    driver.get(query_url + kw)
    time.sleep(3) # Allow 2 seconds for the web page opening
    scroll_pause_time = 5
    screen_height = driver.execute_script("return window.screen.height;")
    scroll_height = driver.execute_script("return document.documentElement.scrollHeight;")
    while (1):
        driver.execute_script("window.scrollTo(0, {scroll_height});".format(scroll_height = scroll_height)) #拉到底
        old_scroll_height = scroll_height
        time.sleep(scroll_pause_time) #等待加载
        scroll_height = driver.execute_script("return document.documentElement.scrollHeight;") #获取新的最大距离
        if old_scroll_height >= scroll_height: #如果再下拉一屏幕就出界了，就停止下拉
            break
    soup = BeautifulSoup(driver.page_source, "html.parser")
    msgs = soup.select("a", class_="yt-simple-endpoint style-scope ytd-watch-card-compact-video-renderer")
    last_msg = ""
    for msg in msgs:
        link = msg.get('href')
        if link!= None and len(link)>=6:
            if link[1:6]=="watch":
                global video_count
                if last_msg != link:
                    video_count += 1
                    form = "https://www.youtube.com"
                    file.write(form + link + '\n')
                    last_msg = link
                else:
                    continue
        #print(result)
        #print("total=",video_count)
        if video_count>=5000:
            break
    print("video_count=",video_count)
    file.close()

def videoDetail(video_url):#go through the list to scrap info of each video
    # if this video has already been created,quit;else create a new json file
    token = video_url[-11:]
    if os.path.exists('./video/' + token + '.json'):
        print("this video has already been scraped.")
        return
    else:
        time.sleep(2)
        response = requests.get(video_url,headers = headers)
        soup = BeautifulSoup(response.text, features='html.parser')
        info = {}
        info["title"] = soup.select_one('meta[itemprop="name"][content]')['content']
        info["url"] = video_url
        info["image"] = soup.select_one('meta[property="og:image"][content]')['content']
        info["author"] = soup.select_one('link[itemprop="name"][content]')['content']
        info["viewCount"] = soup.select_one('meta[itemprop="interactionCount"][content]')['content'] #views
        info["datePublished"] = soup.select_one('meta[itemprop="datePublished"][content]')['content']
        findLikes = re.search(f'[^s]like this video along with[ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*',str(soup))
        if findLikes == None:
            info['likes'] = '0'
        else:
            likeStr = findLikes.group(0)[1:]
            info['likes'] = re.search(f'[,0-9]+$',likeStr).group(0)
        findDislikes = re.search(f'dislike this video along with[ ]*[ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*[^ ]*',str(soup)) 
        if findDislikes == None:
            info['dislikes'] = '0'
        else:
            disLikeStr = findDislikes.group(0)
            info['dislikes'] = re.search(f'[,0-9]+$',disLikeStr).group(0)
        comm = []
        com_cnt = 0
        #print(soup.prettify)
        opts = Options()
        opts.headless = False
        driver = webdriver.Chrome(options=opts)
        driver.get(video_url)
        driver.execute_script('window.scrollTo(1, 500);')
        #now wait let load the comments
        time.sleep(4)
        driver.execute_script('window.scrollTo(1, 1500);')
        # find comments
        comment_div=driver.find_element_by_xpath('//*[@id="contents"]')
        comments=comment_div.find_elements_by_xpath('//*[@id="content-text"]')
        for comment in comments:
            if (com_cnt<5):
                comm.append(comment.text)
                com_cnt+=1
            else:
                break
        info['comment'] = comm
        # find authorLink
        authorLink_class = driver.find_element_by_xpath('//*[@id="top-row"]/ytd-video-owner-renderer/a')
        authorLink =authorLink_class.get_attribute('href')
        if authorLink[0:32]!="https://www.youtube.com/channel/":
            driver.quit()
            #print("this video is posted by weird account.")
            return
            #放弃所有由这种奇怪账号发出的视频呃呃呃
        else:
            author_token = authorLink[-24:]
            info['authorLink'] = authorLink
            # find description of video
            description_div = driver.find_element_by_xpath('//*[@id="description"]')
            description = description_div.find_element_by_xpath('//*[@id="description"]/yt-formatted-string')
            info['description'] = description.text
            #print('author link is',info['authorLink'])
            infoString = json.dumps(info) #将info转化为字符串
            f = open('./video/' + token + '.json', 'w')
            f.write(infoString)
            f.close()

            if os.path.exists('./author/' + author_token + '.json'):
                driver.quit()
                return
            else:
                # create a new author json file
                author_info = {}
                # author name
                author_info['name'] = info['author']
                # follower number
                follower_ele = driver.find_element_by_xpath('//*[@id="owner-sub-count"]')
                follower_raw = follower_ele.get_attribute('textContent')
                reg = re.compile('[.0-9]*[.0-9]*[.0-9]*[.0-9]*[.0-9]*[.0-9]*[.0-9]*')
                follower = re.match(reg,follower_raw).group()  #得到纯数字
                for i in range(1,len(follower)):
                    if follower[i]=='.':
                        follower = follower + 'K'
                author_info['follower'] = follower
                #print(author_info['follower'])
                # author link
                author_info['link'] = authorLink
                # author profile,and profile image
                author_info['image'],author_info['profile'] = getProfile(authorLink)
                #this should suffice
                author_info_str = json.dumps(author_info)
                a_f = open('./author/' + author_token + '.json','w')
                a_f.write(author_info_str)
                a_f.close()
                driver.quit()

def getProfile(author_url):
    opts = Options()
    opts.add_argument('--headless')
    driver = webdriver.Chrome(options=opts)
    driver.get(author_url)
    authorImage = driver.find_element_by_xpath('//*[@id="img"]').get_attribute('src')
    about_driver = webdriver.Chrome(options=opts)
    about_driver.get(author_url + '/about')
    profile = about_driver.find_element_by_xpath('//*[@id="description"]').find_element_by_xpath('//*[@id="description"]').text
    driver.quit()
    about_driver.quit()
    return (authorImage,profile)

def getAuthor(author_url):
    f = open("temp.text" ,'a')
    driver = webdriver.Chrome()
    driver.get(author_url)
    time.sleep(3) # Allow 2 seconds for the web page opening
    scroll_pause_time = 5
    screen_height = driver.execute_script("return window.screen.height;")
    scroll_height = driver.execute_script("return document.documentElement.scrollHeight;")
    while (1):
        driver.execute_script("window.scrollTo(0, {scroll_height});".format(scroll_height = scroll_height)) #拉到底
        old_scroll_height = scroll_height
        time.sleep(scroll_pause_time) #等待加载
        scroll_height = driver.execute_script("return document.documentElement.scrollHeight;") #获取新的最大距离
        if old_scroll_height >= scroll_height: #如果再下拉一屏幕就出界了，就停止下拉
            break
    soup = BeautifulSoup(driver.page_source,'html.parser')
    msgs = soup.select('#video-title', class_="yt-simple-endpoint style-scope ytd-grid-video-renderer")
    last_msg = ""
    for msg in msgs:
        link = msg.get('href')
        if link!= None and len(link)>=6:
            if link[1:6]=="watch":
                global video_count
                if last_msg != link:
                    video_count += 1
                    form = "https://www.youtube.com"
                    f.write(form + link + '\n')
                    last_msg = link
                else:
                    continue
    driver.quit()

if __name__ == '__main__': 
    '''   
    f = open('urls.text','w')
    f.close()
    urlsOfVideo('person+of+interest')
    urlsOfVideo('american+horror+story')
    urlsOfVideo('good+omens')
    ''' 
    f = open('urls.text','r')
    for line in f.readlines():
        line = line.strip()
        videoDetail(line)
    f.close()
     

