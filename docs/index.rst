.. snscrape documentation master file, created by
   sphinx-quickstart on Sat Dec 11 06:18:23 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to snscrape's documentation!
====================================

``snscrape`` is a scraper for social networking services (SNS). It scrapes through things like user profiles, hashtags, or searches and returns the discovered items, usually posts. ``snscrape`` supports several SNS:

================== =======================================================
Platform           Can scrape for items in:
================== =======================================================
Twitter            User profile, hashtag, search, thread, list, trending
Instagram          User profile, hashtag, location
Reddit             User profile, subreddit, search (via Pushshift)
Facebook           User profile, group, community (for visitor posts)
Telegram           Channel
VKontakte          User profile
Weibo (Sina Weibo) User profile
================== =======================================================

``snscrape`` works without the need for logins/authentications. The drawback of doing so, however, is that some platforms (right now, or in the future) may try to impose limits for unathenticated or not-logged-in requests coming from your IP address. Such IP-based limits are usually temporary.

``snscrape`` can be used either from CLI or imported as a library.

CLI usage
---------

The generic syntax of snscrape's CLI is: ::

	snscrape [GLOBAL-OPTIONS] SCRAPER-NAME [SCRAPER-OPTIONS] [SCRAPER-ARGUMENTS...]

``snscrape --help`` and ``snscrape SCRAPER-NAME --help`` provide details on the options and arguments. ``snscrape --help`` also lists all available scrapers.

The default output of the CLI is the URL of each result.

Some noteworthy global options are:

* ``--jsonl`` to get output as JSONL. This includes all information extracted by ``snscrape`` (e.g. message content, datetime, images; details vary by scraper).
* ``--max-results NUMBER`` to only return the first ``NUMBER`` results.
* ``--with-entity`` to get an item on the entity being scraped, e.g. the user or channel. This is not supported on all scrapers. (You can use this together with ``--max-results 0`` to only fetch the entity info.)

**Examples**

.. examples go here

Library usage
-------------

The general idea of steps is:

#. **Instantiate a scraper object.**
	``snscrape`` provides various object classes that implement their own specific ways. For example, :class:`TwitterSearchScraper` gathers tweets via search query, and :class:`TwitterUserScraper` gathers tweets from a specified user.
#. **Call the scraper's** ``get_item()`` **method.**
	``get_item()`` is an iterator and yields one item at a time.

Each scraper class provides different options and arguments. Refer to the class signature for more information, e.g. in Jupyter Notebook it can be done via ::

	?TwitterSearchScraper

**Examples**

.. examples go here

API reference
=============

.. toctree::
	:maxdepth: 2

	api-reference

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
