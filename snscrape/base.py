import abc
import copy
import dataclasses
import datetime
import functools
import json
import logging
import requests
import time
import warnings


logger = logging.getLogger(__name__)


class _DeprecatedProperty:
	def __init__(self, name, repl, replStr):
		self.name = name
		self.repl = repl
		self.replStr = replStr

	def __get__(self, obj, objType):
		if obj is None: # if the access is through the class using _DeprecatedProperty rather than an instance of the class:
			return self
		warnings.warn(f'{self.name} is deprecated, use {self.replStr} instead', FutureWarning, stacklevel = 2)
		return self.repl(obj)


def _json_serialise_datetime(obj):
	'''A JSON serialiser that converts datetime.datetime and datetime.date objects to ISO-8601 strings.'''
	if isinstance(obj, (datetime.datetime, datetime.date)):
		return obj.isoformat()
	raise TypeError(f'Object of type {type(obj)} is not JSON serializable')


def _json_dataclass_to_dict(obj):
	if isinstance(obj, _JSONDataclass) or dataclasses.is_dataclass(obj):
		out = {}
		out['_type'] = f'{type(obj).__module__}.{type(obj).__name__}'
		for field in dataclasses.fields(obj):
			assert field.name != '_type'
			out[field.name] = _json_dataclass_to_dict(getattr(obj, field.name))
		# Add in (non-deprecated) properties
		for k in dir(obj):
			if isinstance(getattr(type(obj), k, None), property):
				assert k != '_type'
				out[k] = _json_dataclass_to_dict(getattr(obj, k))
		return out
	elif isinstance(obj, (tuple, list)):
		return type(obj)(_json_dataclass_to_dict(x) for x in obj)
	elif isinstance(obj, dict):
		return {_json_dataclass_to_dict(k): _json_dataclass_to_dict(v) for k, v in obj.items()}
	elif isinstance(obj, set):
		return {_json_dataclass_to_dict(v) for v in obj}
	else:
		return copy.deepcopy(obj)


@dataclasses.dataclass
class _JSONDataclass:
	'''A base class for dataclasses for conversion to JSON'''

	def json(self):
		'''Convert the object to a JSON string'''
		out = _json_dataclass_to_dict(self)
		for key, value in list(out.items()): # Modifying the dict below, so make a copy first
			if isinstance(value, IntWithGranularity):
				out[key] = int(value)
				assert f'{key}.granularity' not in out, f'Granularity collision on {key}.granularity'
				out[f'{key}.granularity'] = value.granularity
		return json.dumps(out, default = _json_serialise_datetime)


@dataclasses.dataclass
class Item(_JSONDataclass):
	'''An abstract base class for an item returned by the scraper's get_items generator.

	An item can really be anything. The string representation should be useful for the CLI output (e.g. a direct URL for the item).'''

	@abc.abstractmethod
	def __str__(self):
		pass


@dataclasses.dataclass
class Entity(_JSONDataclass):
	'''An abstract base class for an entity returned by the scraper's entity property.

	An entity is typically the account of a person or organisation. The string representation should be the preferred direct URL to the entity's page on the network.'''

	@abc.abstractmethod
	def __str__(self):
		pass


class IntWithGranularity(int):
	'''A number with an associated granularity

	For example, an IntWithGranularity(42000, 1000) represents a number on the order of 42000 with two significant digits, i.e. something counted with a granularity of 1000.'''

	def __new__(cls, value, granularity, *args, **kwargs):
		obj = super().__new__(cls, value, *args, **kwargs)
		obj.granularity = granularity
		return obj

	def __reduce__(self):
		return (IntWithGranularity, (int(self), self.granularity))


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

	def _get_entity(self):
		'''Get the entity behind the scraper, if any.

		This is the method implemented by subclasses for doing the actual retrieval/entity object creation. For accessing the scraper's entity, use the entity property.'''
		return None

	@functools.cached_property
	def entity(self):
		return self._get_entity()

	def _request(self, method, url, params = None, data = None, headers = None, timeout = 10, responseOkCallback = None, allowRedirects = True):
		for attempt in range(self._retries + 1):
			# The request is newly prepared on each retry because of potential cookie updates.
			req = self._session.prepare_request(requests.Request(method, url, params = params, data = data, headers = headers))
			logger.info(f'Retrieving {req.url}')
			logger.debug(f'... with headers: {headers!r}')
			if data:
				logger.debug(f'... with data: {data!r}')
			try:
				r = self._session.send(req, allow_redirects = allowRedirects, timeout = timeout)
			except requests.exceptions.RequestException as exc:
				if attempt < self._retries:
					retrying = ', retrying'
					level = logging.INFO
				else:
					retrying = ''
					level = logging.ERROR
				logger.log(level, f'Error retrieving {req.url}: {exc!r}{retrying}')
			else:
				redirected = f' (redirected to {r.url})' if r.history else ''
				logger.info(f'Retrieved {req.url}{redirected}: {r.status_code}')
				if r.history:
					for i, redirect in enumerate(r.history):
						logger.debug(f'... request {i}: {redirect.request.url}: {r.status_code} (Location: {r.headers.get("Location")})')
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
						level = logging.INFO
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
	def setup_parser(cls, subparser):
		pass

	@classmethod
	def from_args(cls, args):
		return cls._construct(args)

	@classmethod
	def _construct(cls, argparseArgs, *args, **kwargs):
		return cls(*args, **kwargs, retries = argparseArgs.retries)


def nonempty_string(name):
	def f(s):
		s = s.strip()
		if s:
			return s
		raise ValueError('must not be an empty string')
	f.__name__ = name
	return f
