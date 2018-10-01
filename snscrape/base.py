import abc
import logging
import requests
import time


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
		self._session = requests.Session()

	@abc.abstractmethod
	def get_items(self):
		'''Iterator yielding Items.'''
		pass

	def _request(self, method, url, params = None, data = None, headers = None, timeout = 10, responseOkCallback = None):
		for attempt in range(self._retries + 1):
			# The request is newly prepared on each retry because of potential cookie updates.
			req = self._session.prepare_request(requests.Request(method, url, params = params, data = data, headers = headers))
			logger.info(f'Retrieving {req.url}')
			logger.debug(f'... with headers: {headers!r}')
			if data:
				logger.debug(f'... with data: {data!r}')
			try:
				r = self._session.send(req, timeout = timeout)
			except requests.exceptions.RequestException as exc:
				if attempt < self._retries:
					retrying = ', retrying'
					level = logging.WARNING
				else:
					retrying = ''
					level = logging.ERROR
				logger.log(level, f'Error retrieving {req.url}: {exc!r}{retrying}')
			else:
				if responseOkCallback is not None:
					success, msg = responseOkCallback(r)
				else:
					success, msg = (True, None)
				msg = f': {msg}' if msg else ''

				if success:
					logger.debug(f'{req.url} retrieved successfully{msg}')
					return r
				else:
					if attempt < self._retries:
						retrying = ', retrying'
						level = logging.WARNING
					else:
						retrying = ''
						level = logging.ERROR
					logger.log(level, f'Error retrieving {req.url}{msg}{retrying}')
			if attempt < self._retries:
				sleepTime = 1.0 * 2**attempt # exponential backoff: sleep 1 second after first attempt, 2 after second, 4 after third, etc.
				logger.info(f'Waiting {sleepTime:.0f} seconds')
				time.sleep(sleepTime)
		else:
			msg = f'{self._retries + 1} requests to {req.url} failed, giving up.'
			logger.fatal(msg)
			raise ScraperException(msg)
		raise RuntimeError('Reached unreachable code')

	def _get(self, *args, **kwargs):
		return self._request('GET', *args, **kwargs)

	def _post(self, *args, **kwargs):
		return self._request('POST', *args, **kwargs)

	@classmethod
	@abc.abstractmethod
	def setup_parser(cls, subparser):
		pass

	@classmethod
	@abc.abstractmethod
	def from_args(cls, args):
		pass
