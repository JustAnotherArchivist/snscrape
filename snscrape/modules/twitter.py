import bs4
import datetime
import json
import random
import logging
import snscrape.base
import typing


logger = logging.getLogger(__name__)


class Tweet(typing.NamedTuple, snscrape.base.Item):
	url: str
	date: datetime.datetime
	content: str

	def __str__(self):
		return self.url


class TwitterSearchScraper(snscrape.base.Scraper):
	name = 'twitter-search'

	def __init__(self, query, **kwargs):
		super().__init__(**kwargs)
		self._query = query

	def _get_feed_from_html(self, html):
		soup = bs4.BeautifulSoup(html, 'lxml')
		feed = soup.find_all('li', 'js-stream-item')
		return feed

	def _feed_to_items(self, feed):
		for tweet in feed:
			username = tweet.find('span', 'username').find('b').text
			tweetID = tweet['data-item-id']
			date = datetime.datetime.fromtimestamp(int(tweet.find('a', 'tweet-timestamp').find('span', '_timestamp')['data-time']), datetime.timezone.utc)
			content = tweet.find('p', 'tweet-text').text
			yield Tweet(f'https://twitter.com/{username}/status/{tweetID}', date, content)

	def _check_json_callback(self, r):
		if r.headers.get('content-type') != 'application/json;charset=utf-8':
			return False, f'content type is not JSON'
		return True, None

	def get_items(self):
		headers = {'User-Agent': f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.{random.randint(1, 3500)}.{random.randint(1, 160)} Safari/537.36'}

		# First page
		logger.info(f'Retrieving search page for {self._query}')
		r = self._get('https://twitter.com/search', params = {'f': 'tweets', 'vertical': 'default', 'lang': 'en', 'q': self._query, 'src': 'typd', 'qf': 'off'}, headers = headers)

		feed = self._get_feed_from_html(r.text)
		if not feed:
			return
		newestID = feed[0]['data-item-id']
		maxPosition = f'TWEET-{feed[-1]["data-item-id"]}-{newestID}'
		yield from self._feed_to_items(feed)

		while True:
			logger.info(f'Retrieving scroll page {maxPosition}')
			r = self._get('https://twitter.com/i/search/timeline',
				params = {
					'f': 'tweets',
					'vertical': 'default',
					'lang': 'en',
					'q': self._query,
					'include_available_features': '1',
					'include_entities': '1',
					'reset_error_state': 'false',
					'src': 'typd',
					'qf': 'off',
					'max_position': maxPosition,
				},
				headers = headers,
				responseOkCallback = self._check_json_callback)

			feed = self._get_feed_from_html(json.loads(r.text)['items_html'])
			if not feed:
				return
			maxPosition = f'TWEET-{feed[-1]["data-item-id"]}-{newestID}'
			yield from self._feed_to_items(feed)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('query', help = 'A Twitter search string')

	@classmethod
	def from_args(cls, args):
		return cls(args.query, retries = args.retries)


class TwitterUserScraper(TwitterSearchScraper):
	name = 'twitter-user'

	def __init__(self, username, **kwargs):
		super().__init__(f'from:{username}', **kwargs)
		self._username = username

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'A Twitter username (without @)')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)

class TwitterHashtagScraper(TwitterSearchScraper):
	name = 'twitter-hashtag'

	def __init__(self, hashtag, **kwargs):
		super().__init__(f'#{hashtag}', **kwargs)
		self._hashtag = hashtag

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('hashtag', help = 'A Twitter hashtag (without #)')

	@classmethod
	def from_args(cls, args):
		return cls(args.hashtag, retries = args.retries)
