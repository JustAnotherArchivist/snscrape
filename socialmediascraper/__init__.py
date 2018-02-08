import abc
import argparse
import bs4
import json
import logging
import requests


logger = logging.getLogger(__name__)


class Item:
	'''An abstract base class for an item returned by the scraper's get_items generator.

	An item can really be anything. The string representation should be useful for the CLI output (e.g. a direct URL for the item).'''

	@abc.abstractmethod
	def __str__(self):
		pass


class URLItem(Item):
	'''A generic item which only holds a URL string.'''

	def __init__(self, url):
		self._url = url

	@property
	def url(self):
		return self._url

	def __str__(self):
		return self._url


class ScraperException(Exception):
	pass


class Scraper:
	'''An abstract base class for a scraper.'''

	name = None

	def __init__(self, retries = 3):
		self._retries = retries

	@abc.abstractmethod
	def get_items(self):
		'''Iterator yielding Items.'''
		pass

	def _get(self, url, params = None, headers = None, responseOkCallback = None):
		for attempt in range(self._retries + 1):
			logger.info(f'Retrieving {url}')
			logger.debug(f'... with parameters: {params!r}')
			logger.debug(f'... with headers: {headers!r}')
			try:
				r = requests.get(url, params = params, headers = headers)
				if responseOkCallback is None or responseOkCallback(r):
					logger.debug(f'{r.request.url} retrieved successfully')
					return r
			except requests.exceptions.RequestException as exc:
				logger.error(f'Error retrieving {url}: {exc!r}')
		else:
			msg = f'{self._retries + 1} requests to {url} failed, giving up.'
			logger.fatal(msg)
			raise ScraperException(msg)
		raise RuntimeError('Reached unreachable code')

	@classmethod
	@abc.abstractmethod
	def setup_parser(cls, subparser):
		pass

	@classmethod
	@abc.abstractmethod
	def from_args(cls, args):
		pass


class TwitterUserTweetsScraper(Scraper):
	name = 'twitter-user-tweets'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username

	def _get_feed_from_html(self, html):
		soup = bs4.BeautifulSoup(html, 'lxml')
		feed = soup.find_all('li', 'js-stream-item')
		return feed

	def _feed_to_items(self, feed):
		for tweet in feed:
			username = tweet.find('span', 'username').find('b').text
			tweetID = tweet['data-item-id']
			yield URLItem(f'https://twitter.com/{username}/status/{tweetID}')

	def _check_json_callback(self, r):
		if r.headers['content-type'] != 'application/json;charset=utf-8':
			logger.error(f'Content type of {r.url} is not JSON')
			return False
		return True

	def get_items(self):
		query = f'from:{self._username}'
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

		# First page
		logger.info(f'Retrieving search page for {query}')
		r = self._get('https://twitter.com/search', params = {'f': 'tweets', 'vertical': 'default', 'lang': 'en', 'q': query, 'src': 'typd'}, headers = headers)

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
					'q': query,
					'include_available_features': '1',
					'include_entities': '1',
					'reset_error_state': 'false',
					'src': 'typd',
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
		subparser.add_argument('username', help = 'A Twitter username (without @)')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)


def parse_args():
	parser = argparse.ArgumentParser(formatter_class = argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument('-v', '--verbose', '--verbosity', dest = 'verbosity', action = 'count', default = 0, help = 'Increase output verbosity')
	parser.add_argument('--retry', '--retries', dest = 'retries', type = int, default = 3, metavar = 'N',
		help = 'When the connection fails or the server returns an unexpected response, retry up to N times with an exponential backoff')
	parser.add_argument('-n', '--max-results', dest = 'maxResults', type = int, metavar = 'N', help = 'Only return the first N results')

	subparsers = parser.add_subparsers(dest = 'scraper', help = 'The scraper you want to use')
	for cls in Scraper.__subclasses__():
		subparser = subparsers.add_parser(cls.name, formatter_class = argparse.ArgumentDefaultsHelpFormatter)
		cls.setup_parser(subparser)
		subparser.set_defaults(cls = cls)

	args = parser.parse_args()

	# http://bugs.python.org/issue16308 / https://bugs.python.org/issue26510 (fixed in Python 3.7)
	if not args.scraper:
		raise RuntimeError('Error: no scraper specified')

	return args


def setup_logging(verbosity):
	rootLogger = logging.getLogger()

	# Set level
	if verbosity > 0:
		level = logging.INFO if verbosity == 1 else logging.DEBUG
		rootLogger.setLevel(level)
		for handler in rootLogger.handlers:
			handler.setLevel(level)

	# Create formatter
	formatter = logging.Formatter('{asctime}  {levelname}  {name}  {message}', datefmt = '%Y-%m-%d %H:%M:%S', style = '{')

	# Add stream handler
	handler = logging.StreamHandler()
	handler.setFormatter(formatter)
	rootLogger.addHandler(handler)


def main():
	args = parse_args()
	setup_logging(args.verbosity)
	scraper = args.cls.from_args(args)

	i = 0
	for i, item in enumerate(scraper.get_items(), start = 1):
		print(item)
		if args.maxResults and i >= args.maxResults:
			logger.info(f'Exiting after {i} results')
			break
	else:
		logger.info(f'Done, found {i} results')
