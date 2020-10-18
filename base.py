from __future__ import annotations
import base64
import collections
import dataclasses
import datetime
import json
import os
import pickle
import requests
import snscrape.base
import time
import unittest


isCapture = os.environ.get('SNSCRAPE_TEST_CAPTURE', None) is not None
JSON_MARKER_PICKLED = 'be72ba74-4543-468c-86f9-c6900de95d58'
JSON_MARKER_DEQUE = '557c81d2-46fc-4925-8969-609b52a8dd40'


def request_to_tuple(request: requests.Request):
	# A tuple of all request attributes that are set/modified by snscrape
	return (request.method, request.url, request.params, request.data, request.headers)


class InterceptiveAdapter(requests.adapters.BaseAdapter):
	def __init__(self,
	             session: 'Session',
	             mode: str,
	             httpData: collections.deque[tuple[requests.Request, requests.Response]],
	             preparedRequestToRequest: dict[requests.PreparedRequest, requests.Request],
	             *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.__session = session
		self.__mode = mode
		self.__httpData = httpData
		self.__preparedRequestToRequest = preparedRequestToRequest

	def send(self, preparedRequest, **kwargs):
		assert preparedRequest in self.__preparedRequestToRequest
		if self.__mode in ('capture', 'live'):
			response = super(Session, self.__session).get_adapter(preparedRequest.url).send(preparedRequest, **kwargs)
			self.__httpData.append((self.__preparedRequestToRequest[preparedRequest], response))
			return response
		else:
			assert self.__httpData, 'unexpected request (no more data)'
			expectedRequest, expectedResponse = self.__httpData.popleft()
			expectedTuple = request_to_tuple(expectedRequest)
			actualTuple = request_to_tuple(self.__preparedRequestToRequest[preparedRequest])
			assert actualTuple == expectedTuple, f'unexpected request (wrong order?); expected {expectedTuple!r}, got {actualTuple!r}'
			return expectedResponse


class Session(requests.Session):
	def __init__(self, mode, httpData, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.__preparedRequestToRequest = {}
		self.__adapter = InterceptiveAdapter(self, mode, httpData, self.__preparedRequestToRequest)

	def prepare_request(self, request, *args, **kwargs):
		preparedRequest = super().prepare_request(request, *args, **kwargs)
		self.__preparedRequestToRequest[preparedRequest] = request
		return preparedRequest

	def get_adapter(self, *args, **kwargs):
		return self.__adapter

	def send(self, preparedRequest, *args, **kwargs):
		response = super().send(preparedRequest, *args, **kwargs)
		del self.__preparedRequestToRequest[preparedRequest]
		return response


OriginalScraper = snscrape.base.Scraper
class TestScraper(OriginalScraper):
	def __init__(self, *args, _testMode: str = None, _testHttpData: collections.deque[tuple[requests.Request, requests.Response]] = None, **kwargs):
		super().__init__(*args, **kwargs)
		self._session = Session(_testMode, _testHttpData)
snscrape.base.Scraper = TestScraper


@dataclasses.dataclass
class ItemsAndEntity:
	items: typing.Optional[list[snscrape.base.Item]] = None
	entity: typing.Optional[snscrape.base.Entity] = None


def encode(obj):
	if isinstance(obj, (requests.Request, requests.Response, snscrape.base.Item, snscrape.base.Entity)):
		return encode((JSON_MARKER_PICKLED, base64.b64encode(pickle.dumps(obj)).decode('ascii')))
	if isinstance(obj, dict):
		return {encode(k): encode(v) for k, v in obj.items()}
	if isinstance(obj, (tuple, list)):
		return type(obj)(encode(v) for v in obj)
	if isinstance(obj, collections.deque):
		return encode((JSON_MARKER_DEQUE, [encode(v) for v in obj]))
	return obj


def dump(obj, fn):
	assert isinstance(obj, dict)
	with open(fn, 'w') as fp:
		fp.write(json.dumps(encode(obj)))


def decode(obj):
	if isinstance(obj, list) and len(obj) == 2:
		if obj[0] == JSON_MARKER_PICKLED:
			return pickle.loads(base64.b64decode(obj[1].encode('ascii')))
		elif obj[0] == JSON_MARKER_DEQUE:
			return collections.deque(decode(obj[1]))
	if isinstance(obj, dict):
		return {decode(k): decode(v) for k, v in obj.items()}
	if isinstance(obj, list):
		return type(obj)(decode(v) for v in obj)
	return obj


def load(fn):
	with open(fn, 'r') as fp:
		obj = json.load(fp)
	assert isinstance(obj, dict)
	return decode(obj)


def filter_attributes(o, skipAttributes: dict[type, tuple[str]]):
	'''Return a deep copy of o with all occurrences of the attributes mentioned in skipAttributes removed.'''
	t = type(o)
	attrs = skipAttributes[t] if t in skipAttributes else next((v for k, v in skipAttributes.items() if isinstance(o, k)), ())
	if dataclasses.is_dataclass(o):
		# Can't just use dataclasses.asdict because we'd lose the type information on nested dataclass instances
		d = {}
		for f in dataclasses.fields(o):
			if f.name in attrs:
				continue
			d[f.name] = filter_attributes(getattr(o, f.name), skipAttributes)
		return d
	if isinstance(o, (tuple, list)):
		return t(filter_attributes(x, skipAttributes) for x in o)
	if isinstance(o, dict):
		o2 = {}
		for k, v in o.items():
			if k in attrs:
				continue
			o2[k] = filter_attributes(v, skipAttributes)
		return o2
	if isinstance(o, (str, int, datetime.datetime)) or o is None:
		return o
	raise NotImplementedError(f'Can\'t filter {o!r}')


class TestCase(unittest.TestCase):
	def run_scraper(self, scraperClass, *args, **kwargs):
		global isCapture
		fn = os.path.join(os.path.dirname(__file__), 'data', f'{self.id()}.json')
		liveEqualityTestSkipAttributes = kwargs.pop('liveEqualityTestSkipAttributes', {})
		if isCapture:
			startTime = time.time()
			httpData = collections.deque()
			scraper = scraperClass(*args, _testMode = 'capture', _testHttpData = httpData, **kwargs)
			itemsAndEntity = ItemsAndEntity()
			yield (scraper, itemsAndEntity)
			endTime = time.time()
			obj = {
				'test': self.id(),
				'startTime': startTime,
				'endTime': endTime,
				'httpData': httpData,
				'items': itemsAndEntity.items,
				'entity': itemsAndEntity.entity,
			}
			dump(obj, fn)
		else:
			capturedObj = load(fn)

			# Regression test
			scraper = scraperClass(*args, _testMode = 'replay', _testHttpData = capturedObj['httpData'], **kwargs)
			replayedItemsAndEntity = ItemsAndEntity()
			yield (scraper, replayedItemsAndEntity)
			self.assertEqual(replayedItemsAndEntity.items, capturedObj['items'])
			self.assertEqual(replayedItemsAndEntity.entity, capturedObj['entity'])

			# Live test
			liveHttpData = collections.deque()
			scraper = scraperClass(*args, _testMode = 'live', _testHttpData = liveHttpData, **kwargs)
			liveItemsAndEntity = ItemsAndEntity()
			yield (scraper, liveItemsAndEntity)
			# Filter out attributes that frequently change
			filteredLiveItems = filter_attributes(liveItemsAndEntity.items, liveEqualityTestSkipAttributes)
			filteredCapturedItems = filter_attributes(capturedObj['items'], liveEqualityTestSkipAttributes)
			filteredLiveEntity = filter_attributes(liveItemsAndEntity.entity, liveEqualityTestSkipAttributes)
			filteredCapturedEntity = filter_attributes(capturedObj['entity'], liveEqualityTestSkipAttributes)
			self.assertEqual(filteredLiveItems, filteredCapturedItems)
			self.assertEqual(filteredLiveEntity, filteredCapturedEntity)

	def run_scraper_default(self, *args, **kwargs):
		for scraper, itemsAndEntity in self.run_scraper(*args, **kwargs):
			itemsAndEntity.entity = scraper.entity
			itemsAndEntity.items = list(scraper.get_items())


if __name__ == '__main__':
	import snscrape._cli
	import sys
	if sys.argv[1] == 'decode':
		obj = load(sys.argv[2])
		print(snscrape._cli._repr('obj', obj))
