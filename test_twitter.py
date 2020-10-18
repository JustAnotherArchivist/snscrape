import base
import collections
import random
import snscrape.modules.twitter


# These attributes frequently change, so skip them if present
LIVE_EQUALITY_TEST_SKIP_ATTRIBUTES = {
	snscrape.modules.twitter.Tweet: ('replyCount', 'retweetCount', 'likeCount', 'quoteCount'),
	snscrape.modules.twitter.User: ('followersCount', 'friendsCount', 'statusesCount', 'favouritesCount', 'listedCount', 'mediaCount'),
}


class TwitterSearchScraperTestCase(base.TestCase):
	def setUp(self):
		# Fix the random UA used by the Twitter scraper
		random.seed(4) # Chosen by fair dice roll. Guaranteed to be random.

	def run_scraper(self, *args, **kwargs):
		if 'liveEqualityTestSkipAttributes' not in kwargs:
			kwargs['liveEqualityTestSkipAttributes'] = LIVE_EQUALITY_TEST_SKIP_ATTRIBUTES
		yield from super().run_scraper(*args, **kwargs)
