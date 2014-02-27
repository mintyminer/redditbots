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
logging.basicConfig(level=logging.DEBUG)

#Some Regex
reddit_link_pattern = re.compile(r'https?://([a-z0-9-]+\.)*reddit\.com(/.*)?')


def make_link(text, url):
    if not url: return text
    return '[{}]({})'.format(text, url)


def format_link(url, label = None):
    result = make_link('SnapShot', url)
    if label: result = '* {} - {}'.format(label, result)
    return result


def build_comment(links):
    # `links` is a sequence of (URL for snapshot, label for link) pairs
    return '\n'.join(format_link(*link) for link in links) + '\n\n({})'.format(' | '.join(
        make_link(text, url)
        for text, url in (
            ('mirror', None),
            ('open source', 'https://github.com/mintyminer/redditbots'),
            ('create your own snapshots', 'http://redditlog.com')
        )
    ))


def in_database(id):
    return cursor.execute('SELECT id FROM processed WHERE id = ?', (id,)).fetchone() is not None


def add_comment(reddit_interface, id, comment):
    # This is a sanity check. Prevents race conditions and other weird things
    if in_database(id):
        logging.warning('Why is {} being reposted'.format(id))
        return

    try:
        r.get_submission(submission_id = id).add_comment(comment)
    except:
        logging.error('Something went wrong with %s' % id)


def add_to_processed(id):
    cursor.execute('INSERT INTO processed(id) VALUES(?)', (id,))
    db.commit()
    logging.debug('Added %s to database' % id)


def get_reddit_posts(subreddit):
    subreddit_url = "http://www.reddit.com/r/{}/new/.json?sort=new".format(subreddit)
    headers = {'User-Agent': USER_AGENT}
    return requests.get(subreddit_url, headers = headers).json()['data']['children']


def get_snapshot(url):
    payload = {'token': REDDITLOG_TOKEN, 'url': url}
    json = requests.get('http://www.redditlog.com/api/add', params = payload).json()
    if json['status'] != 1: raise ValueError('Failed to upload to redditlog')
    return json['data']['direct_url']

def process_links(html_text):
    html = HTMLParser.HTMLParser().unescape(html_text)
    soup = BeautifulSoup(html)
    for item in soup.find_all('a'):
        link = item.get('href')
        text = item.text

        if not reddit_link_pattern.match(link):
            continue

        if len(text) > 25:
            text = text[:25]+ '...'

        # Borrowed from the old calling code
        text = HTMLParser.HTMLParser().unescape(text)

        # Now we just do the redditlog submission in the inner loop.
        try:
            snapshot_url = get_snapshot(link)
        except:
            continue

        logging.info(snapshot_url)
        yield (snapshot_url, text)


def process_link_post(id, url):
    if not reddit_link_pattern.match(url): return None

    try:
        return build_comment(((get_snapshot(url),),))
        #return build_comment((get_snapshot(url),))
    except:
        return None


def process_self_post(id, body):
    # Look how much simpler this becomes with proper organization.
    links = list(process_links(body))
    return build_comment(links) if links else None


def process_post(reddit_interface, post):
    id = post['id']

    if in_database(id):
        logging.debug('Post Id: {} has already been processed'.format('id'))
        return

    if post['selftext']:
        logging.debug(id + ' is self post')
        comment = process_self_post(id, post['selftext_html'])
    else:
        logging.debug(id + ' is link post')
        comment = process_link_post(id, post['url'])

    if comment:
        add_comment(reddit_interface, id, comment)

    add_to_processed(id)


def main(reddit_interface):
    for subreddit in SUBREDDIT_LIST:
        try:
            posts = get_reddit_posts(subreddit)
            logging.debug(posts)
        except:
            logging.error('Posts for %s did not load' % (subreddit))
            continue

        for post in posts:
            logging.info(post['data']['id'])
            process_post(reddit_interface, post['data'])


if __name__ == '__main__':

    ###Setup###

    #Connect to database
    db = sqlite3.connect(os.path.dirname(os.path.abspath(__file__)) + '/' +config['database_file'])
    cursor = db.cursor()

    #Setup database table if it doesnt exist
    cursor.execute('CREATE TABLE IF NOT EXISTS processed(id CHAR(10), timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, UNIQUE(id) ON CONFLICT ABORT)')


    # Connect to Reddit.
    try:
        r = praw.Reddit(user_agent = USER_AGENT)
        r.login(REDDIT_USERNAME, REDDIT_PASSWORD)
    except praw.errors.InvalidUser:
        logging.error('Invalid User. Could not log onto reddit.')
    except praw.errors.InvalidUserPass:
        logging.error('Invalid Password. Could not log onto reddit.')
    except:
        logging.error('Could not log into reddit for some reason. Exiting Program')
    else: #Once connected to reddit run main program.
        main(r)
    finally: # TODO: see if this can be handled with context managers.
        cursor.close()
        db.close()
