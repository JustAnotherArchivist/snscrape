Examples to scrape Twitter
==========================

.. module:: :noindex:snscrape.modules.twitter

This document will demonstrate example codes to show how snscrape
can be used to scrape tweets.

General idea
------------

The general idea of steps to use snscrape is:

#. **Instantiate a scraper object.** snscrape provides various object classes
   that implement their own specific ways to scrape Twitter. For example,
   :class:`TwitterSearchScraper` gathers tweets via search query, and
   :class:`TwitterUserScraper` gathers tweets from a specified user.
#. **Call the scraper's** ``get_item()`` **method.** 
   ``get_item()`` yields one tweet at a time.

Instantiate the scraper object
------------------------------

The first step is to instantiate the scraper object. 

The following code demonstrates how to instantiate several scraper objects
to scrape Twitter available in snscrape. ::

    # Import twitter module
    from snscrape.modules import twitter

    # We are interested in scraping through search query "omicron variant"
    search_scraper = twitter.TwitterSearchScraper('omicron variant')

    # We are interested in scraping through hashtag "#OmicronVariant"
    # Provide the hashtag without the # sign
    hashtag_scraper = twitter.TwitterHashtagScraper('OmicronVariant')

    # We are interested in collecting tweets by World Health Organization
    # Provide the username without @ sign
    user_scraper = twitter.TwitterUserScraper('WHO', isUserId = False)

    # Alternatively, you also can provide a user ID for that username
    # This is equivalent as above. Internally, user ID will be converted to
    # username.
    user_scraper = twitter.TwitterUserScraper('14499829', isUserId = True)

Perform the scraping
------------------------------------

After instantiating the scraper with the desired parameters, it's time to 
call scraper's `get_item()` method. It yields one tweet at a time and the
number of tweets that will be scraped can't be known beforehand, so you should
be mindful about it. You can iterate through this generator. ::

    results = []
    count = 0
    MAX_COUNT = 1000

    for tweet in search_scraper.get_item():
        results.append(tweet)
        
        count += 1
        if count >= MAX_COUNT:
            break

You can also do something on-the-fly while the tweets are getting received. 
For example, take only the tweet content, tweeter's display name, and 
tweet's like count: ::

    for tweet in search_scraper.get_item():
        results.append(
            (tweet.user.displayname, tweet.content, tweet.likeCount)
        )
