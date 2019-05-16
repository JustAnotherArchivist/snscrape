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
	outlinks: list
	outlinksss: str
	tcooutlinks: list
	tcooutlinksss: str

	def __str__(self):
		return self.url


class TwitterSearchScraper(snscrape.base.Scraper):
	name = 'twitter-search'

	def __init__(self, query, maxPosition = None, **kwargs):
		super().__init__(**kwargs)
		self._query = query
		self._maxPosition = maxPosition

	def _get_feed_from_html(self, html):
		soup = bs4.BeautifulSoup(html, 'lxml')
		feed = soup.find_all('li', 'js-stream-item')
		return feed

	def _feed_to_items(self, feed):
		for tweet in feed:
			username = tweet.find('span', 'username').find('b').text
			tweetID = tweet['data-item-id']
			date = datetime.datetime.fromtimestamp(int(tweet.find('a', 'tweet-timestamp').find('span', '_timestamp')['data-time']), datetime.timezone.utc)
			contentP = tweet.find('p', 'tweet-text')
			content = contentP.text
			outlinks = []
			tcooutlinks = []
			for a in contentP.find_all('a'):
				if a.has_attr('href') and not a['href'].startswith('/') and (not a.has_attr('class') or 'u-hidden' not in a['class']):
					outlinks.append(a['data-expanded-url'])
					tcooutlinks.append(a['href'])
			card = tweet.find('div', 'card2')
			if card and 'has-autoplayable-media' not in card['class']:
				for div in card.find_all('div'):
					if div.has_attr('data-card-url'):
						outlinks.append(div['data-card-url'])
						tcooutlinks.append(div['data-card-url'])
			outlinks = list(dict.fromkeys(outlinks)) # Deduplicate in case the same link was shared more than once within this tweet; may change order on Python 3.6 or older
			tcooutlinks = list(dict.fromkeys(tcooutlinks))
			yield Tweet(f'https://twitter.com/{username}/status/{tweetID}', date, content, outlinks, ' '.join(outlinks), tcooutlinks, ' '.join(tcooutlinks))

	def _check_json_callback(self, r):
		if r.headers.get('content-type') != 'application/json;charset=utf-8':
			return False, f'content type is not JSON'
		return True, None

	def get_items(self):
		headers = {'User-Agent': f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.{random.randint(1, 3500)}.{random.randint(1, 160)} Safari/537.36'}

		# First page
		if self._maxPosition is None:
			logger.info(f'Retrieving search page for {self._query}')
			r = self._get('https://twitter.com/search', params = {'f': 'tweets', 'vertical': 'default', 'lang': 'en', 'q': self._query, 'src': 'spxr', 'qf': 'off'}, headers = headers)

			feed = self._get_feed_from_html(r.text)
			if not feed:
				return
			yield from self._feed_to_items(feed)
			newestID = feed[0]['data-item-id']
			maxPosition = f'TWEET-{feed[-1]["data-item-id"]}-{newestID}'
		else:
			_, _, newestID = self._maxPosition.split('-')
			maxPosition = self._maxPosition

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
					'src': 'spxr',
					'qf': 'off',
					'max_position': maxPosition,
				},
				headers = headers,
				responseOkCallback = self._check_json_callback)

			feed = self._get_feed_from_html(json.loads(r.text)['items_html'])
			if not feed:
				return
			yield from self._feed_to_items(feed)
			maxPosition = f'TWEET-{feed[-1]["data-item-id"]}-{newestID}'

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('--max-position', metavar = 'POSITION', dest = 'maxPosition')
		subparser.add_argument('query', help = 'A Twitter search string')

	@classmethod
	def from_args(cls, args):
		return cls(args.query, maxPosition = args.maxPosition, retries = args.retries)


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
