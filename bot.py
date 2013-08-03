#!/usr/bin/python

#Released under an MIT License by mintyminer. Code available at https://github.com/mintyminer/redditbots

import os
import logging
import praw
import requests
import re
import HTMLParser
import sqlite3
from bs4 import BeautifulSoup

#Import Config File
from config import config

# Get config values
REDDIT_USERNAME = config['reddit_username']
REDDIT_PASSWORD = config['reddit_password']
USER_AGENT = config['user_agent']
REDDITLOG_TOKEN = config['redditlog_token']
SUBREDDIT_LIST = config['subreddit_list']


#Logging Settings
logging.basicConfig(level=logging.INFO)

def add_comment(id,comment):
    #This is a sanity check. Prevents race conditions and other weird things
    if not cursor.execute('SELECT id FROM processed WHERE id = ?',(id,)).fetchone() == None:
        logging.warning('Why is %s being reposted'%id)
        return
    try:
        comment += """

(Mirror | [open source](https://github.com/mintyminer/redditbots) | [create your own snapshots](http://redditlog.com))
        """

        submission = r.get_submission(submission_id=id)
        submission.add_comment(comment)
    except:
        logging.error('Something went wrong with %s' %id)


def check_link(link):
    """Checks link to make sure its from reddit.com, return true if it is"""
    if re.findall(r'https?://([a-z0-9-]+\.)*reddit\.com(/.*)?', link) != []:
        return True
    else:
        return False


def add_to_processed(id):
    cursor.execute('INSERT INTO processed(id) VALUES(?)',(id,))
    db.commit()
    logging.debug('Added %s to database' %id)


def get_reddit_posts(subreddit):
    subreddit_url = "http://www.reddit.com/r/"+subreddit+"/new/.json?sort=new"
    request = requests.get(subreddit_url, headers={'User-Agent': USER_AGENT})
    if request.status_code == 200:
        data = request.json()
        return data['data']['children']
    else:
        return False

def get_snapshot(url):
    payload = {'token':REDDITLOG_TOKEN,'url':url}
    request = requests.get('http://www.redditlog.com/api/add', params=payload)

    if request.status_code == 200 and request.json()['status'] == 1:
        return request.json()['data']['direct_url']
    else:
        return False

def extract_links_old(html_text):
    link_list = []
    html_text = html_text.encode('utf-8')
    links = re.findall(r'(?<=href=")([^"]+)"&gt;(.*?)\b&lt;', str(html_text))
    if links != []:
        for link in links:
            link = list(link)
            if link[0][:1] == '/':
                link[0] = 'http://www.reddit.com' + link[0]
            if check_link(link[0]) == True:
                link_list.append(link)
    logging.debug(link_list)
    return link_list

def extract_links(html_text):
    link_list = []
    html = HTMLParser.HTMLParser().unescape(html_text)
    soup = BeautifulSoup(html)
    for item in soup.find_all('a'):
        link = item.get('href')
        text =  item.text

        if check_link(link) == False:
            continue

        if link[0] == '/':
            link = 'http://reddit.com'+link

        if len(text) > 25:
            text = text[0:25]+ '...'

        link_list.append([text,link])

    return link_list

def process_link_post(post):
    if check_link(post['url']):
        snapshot_url = get_snapshot(post['url'])
        if snapshot_url:
            comment = """[SnapShot](%s)""" % (snapshot_url)
            add_comment(post['id'],comment)


def process_self_post(post):
            has_links = 0

            #Extract links with title
            links = extract_links(post['selftext_html'])

            if links:
                #Set message as empty
                reddit_text = ''

                #Foreach link
                for link in links:
                    #Get data
                    link_text = HTMLParser.HTMLParser().unescape(link[0]) #unescape the html characters in text
                    link_url = link[1]

                    #If url matchs reddit
                    if check_link(link_url) == True:
                        snapshot_url = get_snapshot(link_url)
                        if not snapshot_url:
                            continue
                        has_links = 1
                        print snapshot_url
                        reddit_text += """
* %s - [Snapshot](%s)""" % (link_text, snapshot_url)
                if has_links == 1 and reddit_text != '':
                    #Send comment to reddit
                    add_comment(post['id'],reddit_text)

def process_post(post):
    id = post['id']

    if not cursor.execute('SELECT id FROM processed WHERE id = ?',(id,)).fetchone() == None:
        logging.debug('Post Id; %s has already been processed' %(id))
        return

    if post['selftext']:
        logging.debug(id +' is self post')
        process_self_post(post)
    else:
        logging.debug(id + 'is link post')
        process_link_post(post)

    add_to_processed(id)



def go():
    for subreddit in SUBREDDIT_LIST:
        posts = get_reddit_posts(subreddit)
        if not posts:
            logging.error('Posts for %s did not load'%(subreddit))
            continue

        for post in posts:
                logging.info(post['data']['id'])
                process_post(post['data'])




if __name__ == '__main__':

    ###Setup###

    #Connect to database
    db = sqlite3.connect(os.path.dirname(os.path.abspath(__file__)) + '/' +config['database_file'])
    cursor = db.cursor()

    #Setup database table if it doesnt exist
    cursor.execute('CREATE TABLE IF NOT EXISTS processed(id CHAR(10), timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(id) ON CONFLICT ABORT)')

    #Connect to Reddit
    try:
        r = praw.Reddit(user_agent=USER_AGENT)
        r.login(REDDIT_USERNAME, REDDIT_PASSWORD)
    except praw.errors.InvalidUser:
        logging.error('Invalid User. Could not log onto reddit.')
        exit()
    except praw.errors.InvalidUserPass:
        logging.warning('Invalid User. Could not log into reddit.')
        exit()
    except:
        logging.warning('Could not log into reddit for some reason. Exiting Program')
        exit()

    #Run program
    go()

    #Close DB Connection
    cursor.close()
    db.close()
