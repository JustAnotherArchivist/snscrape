import abc
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
