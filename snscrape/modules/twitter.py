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
	id: int
	username: str
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

	def _get_feed_from_html(self, html, withMinPosition):
		soup = bs4.BeautifulSoup(html, 'lxml')
		feed = soup.find_all('li', 'js-stream-item')
		if withMinPosition:
			streamContainer = soup.find('div', 'stream-container')
			if not streamContainer or not streamContainer.has_attr('data-min-position'):
				if soup.find('div', 'SearchEmptyTimeline'):
					# No results found
					minPosition = None
				else:
					# Unknown error condition
					raise RuntimeError('Unable to find min-position')
			else:
				minPosition = streamContainer['data-min-position']
		else:
			minPosition = None
		return feed, minPosition

	def _feed_to_items(self, feed):
		for tweet in feed:
			username = tweet.find('span', 'username').find('b').text
			tweetID = tweet['data-item-id']
			url = f'https://twitter.com/{username}/status/{tweetID}'

			date = None
			timestampA = tweet.find('a', 'tweet-timestamp')
			if timestampA:
				timestampSpan = timestampA.find('span', '_timestamp')
				if timestampSpan and timestampSpan.has_attr('data-time'):
					date = datetime.datetime.fromtimestamp(int(timestampSpan['data-time']), datetime.timezone.utc)
			if not date:
				logger.warning(f'Failed to extract date for {url}')

			contentP = tweet.find('p', 'tweet-text')
			content = None
			outlinks = []
			tcooutlinks = []
			if contentP:
				content = contentP.text
				for a in contentP.find_all('a'):
					if a.has_attr('href') and not a['href'].startswith('/') and (not a.has_attr('class') or 'u-hidden' not in a['class']):
						if a.has_attr('data-expanded-url'):
							outlinks.append(a['data-expanded-url'])
						else:
							logger.warning(f'Ignoring link without expanded URL on {url}: {a["href"]}')
						tcooutlinks.append(a['href'])
			else:
				logger.warning(f'Failed to extract content for {url}')
			card = tweet.find('div', 'card2')
			if card and 'has-autoplayable-media' not in card['class']:
				for div in card.find_all('div'):
					if div.has_attr('data-card-url'):
						outlinks.append(div['data-card-url'])
						tcooutlinks.append(div['data-card-url'])
			outlinks = list(dict.fromkeys(outlinks)) # Deduplicate in case the same link was shared more than once within this tweet; may change order on Python 3.6 or older
			tcooutlinks = list(dict.fromkeys(tcooutlinks))
			yield Tweet(url, date, content, tweetID, username, outlinks, ' '.join(outlinks), tcooutlinks, ' '.join(tcooutlinks))

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

			feed, maxPosition = self._get_feed_from_html(r.text, True)
			if not feed:
				logger.warning(f'No results for {self._query}')
				return
			yield from self._feed_to_items(feed)
		else:
			maxPosition = self._maxPosition

		if not maxPosition:
			return

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

			obj = json.loads(r.text)
			feed, _ = self._get_feed_from_html(obj['items_html'], False)
			if feed:
				yield from self._feed_to_items(feed)
			if obj['min_position'] == maxPosition:
				return
			maxPosition = obj['min_position']

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
