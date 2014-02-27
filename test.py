#!/usr/bin/python

#Released under an MIT License by mintyminer. Code available at https://github.com/mintyminer/redditbots

import unittest

from bot import *


class RedditLinkTest(unittest.TestCase):

    def check_link(self, link):
        return reddit_link_pattern.match(link)

    def test_link_standard_comment_thread(self):
        link = 'http://www.reddit.com/r/redditbot/comments/1z310l/more_testssss/'
        self.assertTrue(self.check_link(link))

    def test_link_standard_sub_comment_thread(self):
        link = 'http://www.reddit.com/r/SubredditDrama/comments/1z2oq6/cool_so_is_this_subreddit_also_called/cfq0cug'
        self.assertTrue(self.check_link(link))

    def test_link_reddit_in_link(self):
        link = 'http://www.google.com?search=reddit.com/comment'
        self.assertFalse(self.check_link(link))

if __name__ == '__main__':
    unittest.main()