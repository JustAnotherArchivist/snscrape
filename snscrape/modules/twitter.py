__all__ = [
	'Tweet', 'Medium', 'Photo', 'VideoVariant', 'Video', 'Gif', 'TextLink', 'Coordinates', 'Place',
	'User', 'UserLabel',
	'Trend',
	'GuestTokenManager',
	'TwitterSearchScraper',
	'TwitterUserScraper',
	'TwitterProfileScraper',
	'TwitterHashtagScraper',
	'TwitterTweetScraperMode',
	'TwitterTweetScraper',
	'TwitterListPostsScraper',
	'TwitterTrendsScraper',
]


import collections
import dataclasses
import datetime
import email.utils
import enum
import filelock
import itertools
import json
import random
import logging
import os
import re
import snscrape.base
import string
import time
import typing
import urllib.parse
import warnings


# DescriptionURL deprecation
_DEPRECATED_NAMES = {'DescriptionURL': 'TextLink'}
def __getattr__(name):
	if name in _DEPRECATED_NAMES:
		warnings.warn(f'{name} is deprecated, use {_DEPRECATED_NAMES[name]} instead', FutureWarning, stacklevel = 2)
		return globals()[_DEPRECATED_NAMES[name]]
	raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
def __dir__():
	return sorted(__all__ + list(_DEPRECATED_NAMES.keys()))


_logger = logging.getLogger(__name__)
_API_AUTHORIZATION_HEADER = 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA'
_globalGuestTokenManager = None
_GUEST_TOKEN_VALIDITY = 10800


@dataclasses.dataclass
class Tweet(snscrape.base.Item):
	url: str
	date: datetime.datetime
	rawContent: str
	renderedContent: str
	id: int
	user: 'User'
	replyCount: int
	retweetCount: int
	likeCount: int
	quoteCount: int
	conversationId: int
	lang: str
	source: str
	sourceUrl: typing.Optional[str] = None
	sourceLabel: typing.Optional[str] = None
	links: typing.Optional[typing.List['TextLink']] = None
	media: typing.Optional[typing.List['Medium']] = None
	retweetedTweet: typing.Optional['Tweet'] = None
	quotedTweet: typing.Optional['Tweet'] = None
	inReplyToTweetId: typing.Optional[int] = None
	inReplyToUser: typing.Optional['User'] = None
	mentionedUsers: typing.Optional[typing.List['User']] = None
	coordinates: typing.Optional['Coordinates'] = None
	place: typing.Optional['Place'] = None
	hashtags: typing.Optional[typing.List[str]] = None
	cashtags: typing.Optional[typing.List[str]] = None
	card: typing.Optional['Card'] = None

	username = snscrape.base._DeprecatedProperty('username', lambda self: self.user.username, 'user.username')
	outlinks = snscrape.base._DeprecatedProperty('outlinks', lambda self: [x.url for x in self.links] if self.links else [], 'links (url attribute)')
	outlinksss = snscrape.base._DeprecatedProperty('outlinksss', lambda self: ' '.join(x.url for x in self.links) if self.links else '', 'links (url attribute)')
	tcooutlinks = snscrape.base._DeprecatedProperty('tcooutlinks', lambda self: [x.tcourl for x in self.links] if self.links else [], 'links (tcourl attribute)')
	tcooutlinksss = snscrape.base._DeprecatedProperty('tcooutlinksss', lambda self: ' '.join(x.tcourl for x in self.links) if self.links else '', 'links (tcourl attribute)')
	content = snscrape.base._DeprecatedProperty('content', lambda self: self.rawContent, 'rawContent')

	def __str__(self):
		return self.url


@dataclasses.dataclass
class TextLink:
	text: typing.Optional[str]
	url: str
	tcourl: str
	indices: typing.Tuple[int, int]


class Medium:
	pass


@dataclasses.dataclass
class Photo(Medium):
	previewUrl: str
	fullUrl: str


@dataclasses.dataclass
class VideoVariant:
	contentType: str
	url: str
	bitrate: typing.Optional[int]


@dataclasses.dataclass
class Video(Medium):
	thumbnailUrl: str
	variants: typing.List[VideoVariant]
	duration: typing.Optional[float] = None
	views: typing.Optional[int] = None


@dataclasses.dataclass
class Gif(Medium):
	thumbnailUrl: str
	variants: typing.List[VideoVariant]


@dataclasses.dataclass
class Coordinates:
	longitude: float
	latitude: float


@dataclasses.dataclass
class Place:
	fullName: str
	name: str
	type: str
	country: str
	countryCode: str


class Card:
	pass


@dataclasses.dataclass
class SummaryCard(Card):
	title: str
	url: str
	description: typing.Optional[str] = None
	thumbnailUrl: typing.Optional[str] = None
	siteUser: typing.Optional['User'] = None
	creatorUser: typing.Optional['User'] = None


@dataclasses.dataclass
class AppCard(SummaryCard):
	pass


@dataclasses.dataclass
class PollCard(Card):
	options: typing.List['PollOption']
	endDate: datetime.datetime
	duration: int
	finalResults: bool
	lastUpdateDate: typing.Optional[datetime.datetime] = None
	medium: typing.Optional[Medium] = None


@dataclasses.dataclass
class PollOption:
	label: str
	count: typing.Optional[int] = None


@dataclasses.dataclass
class PlayerCard(Card):
	title: str
	url: str
	description: typing.Optional[str] = None
	imageUrl: typing.Optional[str] = None
	siteUser: typing.Optional['User'] = None


@dataclasses.dataclass
class PromoConvoCard(Card):
	actions: typing.List['PromoConvoAction']
	thankYouText: str
	medium: Medium
	thankYouUrl: typing.Optional[str] = None
	thankYouTcoUrl: typing.Optional[str] = None
	cover: typing.Optional['Photo'] = None


@dataclasses.dataclass
class PromoConvoAction:
	label: str
	tweet: str


@dataclasses.dataclass
class BroadcastCard(Card):
	id: str
	url: str
	title: str
	state: typing.Optional[str] = None
	broadcaster: typing.Optional['User'] = None
	thumbnailUrl: typing.Optional[str] = None
	source: typing.Optional[str] = None
	siteUser: typing.Optional['User'] = None


@dataclasses.dataclass
class PeriscopeBroadcastCard(Card):
	id: str
	url: str
	title: str
	description: str
	state: str
	totalParticipants: int
	thumbnailUrl: typing.Optional[str] = None
	source: typing.Optional[str] = None
	broadcaster: typing.Optional['User'] = None
	siteUser: typing.Optional['User'] = None


@dataclasses.dataclass
class EventCard(Card):
	event: 'Event'


@dataclasses.dataclass
class Event:
	id: int
	category: str
	photo: Photo
	title: typing.Optional[str] = None
	description: typing.Optional[str] = None

	@property
	def url(self):
		return f'https://twitter.com/i/events/{self.id}'


@dataclasses.dataclass
class NewsletterCard(Card):
	title: str
	description: str
	url: str
	revueAccountId: int
	issueCount: int
	imageUrl: typing.Optional[str] = None


@dataclasses.dataclass
class NewsletterIssueCard(Card):
	newsletterTitle: str
	newsletterDescription: str
	issueTitle: str
	issueNumber: int
	url: str
	revueAccountId: int
	issueDescription: typing.Optional[str] = None
	imageUrl: typing.Optional[str] = None


@dataclasses.dataclass
class AmplifyCard(Card):
	id: str
	video: Video


@dataclasses.dataclass
class AppPlayerCard(Card):
	title: str
	video: Video
	appCategory: str
	playerOwnerId: int
	siteUser: typing.Optional['User'] = None


@dataclasses.dataclass
class SpacesCard(Card):
	url: str
	id: str


@dataclasses.dataclass
class MessageMeCard(Card):
	recipient: 'User'
	url: str
	buttonText: str


UnifiedCardComponentKey = str
UnifiedCardDestinationKey = str
UnifiedCardMediumKey = str
UnifiedCardAppKey = str


@dataclasses.dataclass
class UnifiedCard(Card):
	componentObjects: typing.Dict[UnifiedCardComponentKey, 'UnifiedCardComponentObject']
	destinations: typing.Dict[UnifiedCardDestinationKey, 'UnifiedCardDestination']
	media: typing.Dict[UnifiedCardMediumKey, Medium]
	apps: typing.Optional[typing.Dict[UnifiedCardAppKey, typing.List['UnifiedCardApp']]] = None
	components: typing.Optional[typing.List[UnifiedCardComponentKey]] = None
	swipeableLayoutSlides: typing.Optional[typing.List['UnifiedCardSwipeableLayoutSlide']] = None
	type: typing.Optional[str] = None

	def __post_init__(self):
		if (self.components is None) == (self.swipeableLayoutSlides is None):
			raise ValueError('did not get exactly one of components or swipeableLayoutSlides')
		if self.components and not all(k in self.componentObjects for k in self.components):
			raise ValueError('missing components')
		if self.swipeableLayoutSlides and not all(s.mediumComponentKey in self.componentObjects and s.componentKey in self.componentObjects for s in self.swipeableLayoutSlides):
			raise ValueError('missing components')
		if any(c.destinationKey not in self.destinations for c in self.componentObjects.values() if hasattr(c, 'destinationKey')):
			raise ValueError('missing destinations')
		if any(b.destinationKey not in self.destinations for c in self.componentObjects.values() if isinstance(c, UnifiedCardButtonGroupComponentObject) for b in c.buttons):
			raise ValueError('missing destinations')
		mediaKeys = []
		for c in self.componentObjects.values():
			if isinstance(c, UnifiedCardMediumComponentObject):
				mediaKeys.append(c.mediumKey)
			elif isinstance(c, UnifiedCardSwipeableMediaComponentObject):
				mediaKeys.extend(x.mediumKey for x in c.media)
		mediaKeys.extend(d.mediumKey for d in self.destinations.values() if d.mediumKey is not None)
		mediaKeys.extend(a.iconMediumKey for l in (self.apps.values() if self.apps is not None else []) for a in l if a.iconMediumKey is not None)
		if any(k not in self.media for k in mediaKeys):
			raise ValueError('missing media')
		if any(c.appKey not in self.apps for c in self.componentObjects.values() if hasattr(c, 'appKey')):
			raise ValueError('missing apps')
		if any(d.appKey not in self.apps for d in self.destinations.values() if d.appKey is not None):
			raise ValueError('missing apps')


class UnifiedCardComponentObject:
	pass


@dataclasses.dataclass
class UnifiedCardDetailComponentObject(UnifiedCardComponentObject):
	content: str
	destinationKey: UnifiedCardDestinationKey


@dataclasses.dataclass
class UnifiedCardMediumComponentObject(UnifiedCardComponentObject):
	mediumKey: UnifiedCardMediumKey
	destinationKey: UnifiedCardDestinationKey


@dataclasses.dataclass
class UnifiedCardButtonGroupComponentObject(UnifiedCardComponentObject):
	buttons: typing.List['UnifiedCardButton']


@dataclasses.dataclass
class UnifiedCardButton:
	text: str
	destinationKey: UnifiedCardDestinationKey


@dataclasses.dataclass
class UnifiedCardSwipeableMediaComponentObject(UnifiedCardComponentObject):
	media: typing.List['UnifiedCardSwipeableMediaMedium']


@dataclasses.dataclass
class UnifiedCardSwipeableMediaMedium:
	mediumKey: UnifiedCardMediumKey
	destinationKey: UnifiedCardDestinationKey


@dataclasses.dataclass
class UnifiedCardAppStoreComponentObject(UnifiedCardComponentObject):
	appKey: UnifiedCardAppKey
	destinationKey: UnifiedCardDestinationKey


@dataclasses.dataclass
class UnifiedCardTwitterListDetailsComponentObject(UnifiedCardComponentObject):
	name: str
	memberCount: int
	subscriberCount: int
	user: 'User'
	destinationKey: UnifiedCardDestinationKey


@dataclasses.dataclass
class UnifiedCardTwitterCommunityDetailsComponentObject(UnifiedCardComponentObject):
	name: str
	theme: str
	membersCount: int
	destinationKey: UnifiedCardDestinationKey
	membersFacepile: typing.Optional[typing.List['User']] = None


@dataclasses.dataclass
class UnifiedCardDestination:
	url: typing.Optional[str] = None
	appKey: typing.Optional[UnifiedCardAppKey] = None
	mediumKey: typing.Optional[UnifiedCardMediumKey] = None

	def __post_init__(self):
		if (self.url is None) == (self.appKey is None):
			raise ValueError('did not get exactly one of url and appKey')


@dataclasses.dataclass
class UnifiedCardApp:
	type: str
	id: str
	title: str
	category: str
	countryCode: str
	url: str
	description: typing.Optional[str] = None
	iconMediumKey: typing.Optional[UnifiedCardMediumKey] = None
	size: typing.Optional[int] = None
	installs: typing.Optional[int] = None
	ratingAverage: typing.Optional[float] = None
	ratingCount: typing.Optional[int] = None
	isFree: typing.Optional[bool] = None
	isEditorsChoice: typing.Optional[bool] = None
	hasInAppPurchases: typing.Optional[bool] = None
	hasInAppAds: typing.Optional[bool] = None


@dataclasses.dataclass
class UnifiedCardSwipeableLayoutSlide:
	mediumComponentKey: UnifiedCardComponentKey
	componentKey: UnifiedCardComponentKey


@dataclasses.dataclass
class TweetRef(snscrape.base.Item):
	'''A reference to a tweet for which no proper Tweet object could be produced from the data returned by Twitter'''

	id: int

	def __str__(self):
		return f'https://twitter.com/i/web/status/{self.id}'


@dataclasses.dataclass
class User(snscrape.base.Entity):
	# Most fields can be None if they're not known.

	username: str
	id: int
	displayname: typing.Optional[str] = None
	rawDescription: typing.Optional[str] = None # Raw description with the URL(s) intact
	renderedDescription: typing.Optional[str] = None # Description as it's displayed on the web interface with URLs replaced
	descriptionLinks: typing.Optional[typing.List[TextLink]] = None
	verified: typing.Optional[bool] = None
	created: typing.Optional[datetime.datetime] = None
	followersCount: typing.Optional[int] = None
	friendsCount: typing.Optional[int] = None
	statusesCount: typing.Optional[int] = None
	favouritesCount: typing.Optional[int] = None
	listedCount: typing.Optional[int] = None
	mediaCount: typing.Optional[int] = None
	location: typing.Optional[str] = None
	protected: typing.Optional[bool] = None
	link: typing.Optional[TextLink] = None
	profileImageUrl: typing.Optional[str] = None
	profileBannerUrl: typing.Optional[str] = None
	label: typing.Optional['UserLabel'] = None

	descriptionUrls = snscrape.base._DeprecatedProperty('descriptionUrls', lambda self: self.descriptionLinks, 'descriptionLinks')
	linkUrl = snscrape.base._DeprecatedProperty('linkUrl', lambda self: self.link.url if self.link else None, 'link.url')
	linkTcourl = snscrape.base._DeprecatedProperty('linkTcourl', lambda self: self.link.tcourl if self.link else None, 'link.tcourl')
	description = snscrape.base._DeprecatedProperty('description', lambda self: self.renderedDescription, 'renderedDescription')

	@property
	def url(self):
		return f'https://twitter.com/{self.username}'

	def __str__(self):
		return self.url


@dataclasses.dataclass
class UserLabel:
	description: str
	url: typing.Optional[str] = None
	badgeUrl: typing.Optional[str] = None
	longDescription: typing.Optional[str] = None


@dataclasses.dataclass
class UserRef:
	id: int


@dataclasses.dataclass
class Trend(snscrape.base.Item):
	name: str
	domainContext: str
	metaDescription: typing.Optional[str] = None

	def __str__(self):
		return f'https://twitter.com/search?q={urllib.parse.quote(self.name)}'


class _ScrollDirection(enum.Enum):
	TOP = enum.auto()
	BOTTOM = enum.auto()
	BOTH = enum.auto()


class GuestTokenManager:
	def __init__(self):
		self._token = None
		self._setTime = 0.0

	@property
	def token(self):
		return self._token

	@token.setter
	def token(self, token):
		self._token = token
		self._setTime = time.time()

	@property
	def setTime(self):
		return self._setTime

	def reset(self):
		self._token = None
		self._setTime = 0.0


class _CLIGuestTokenManager(GuestTokenManager):
	def __init__(self):
		super().__init__()
		cacheHome = os.environ.get('XDG_CACHE_HOME')
		if not cacheHome or not os.path.isabs(cacheHome):
			# This should be ${HOME}/.cache, but the HOME environment variable may not exist on non-POSIX-compliant systems.
			# On POSIX-compliant systems, the XDG Base Directory specification is followed exactly since ~ expands to $HOME if it is present.
			cacheHome = os.path.join(os.path.expanduser('~'), '.cache')
		dir = os.path.join(cacheHome, 'snscrape')
		if not os.path.isdir(dir):
			# os.makedirs does not apply mode recursively anymore. https://bugs.python.org/issue42367
			# This ensures that the XDG_CACHE_HOME is created with the right permissions.
			os.makedirs(os.path.dirname(dir), mode = 0o700, exist_ok = True)
			os.mkdir(dir, mode = 0o700)
		self._file = os.path.join(dir, 'cli-twitter-guest-token.json')
		self._lockFile = f'{self._file}.lock'
		self._lock = filelock.FileLock(self._lockFile)

	def _read(self):
		with self._lock:
			if not os.path.exists(self._file):
				return None
			_logger.info(f'Reading guest token from {self._file}')
			with open(self._file, 'r') as fp:
				try:
					o = json.load(fp)
				except json.JSONDecodeError as e:
					_logger.warning(f'Malformed guest token file {self._file}: {e!s}')
					self.reset()
					return None
		self._token = o['token']
		self._setTime = o['setTime']
		if self._setTime < time.time() - _GUEST_TOKEN_VALIDITY:
			_logger.info('Guest token expired')
			self.reset()

	def _write(self):
		with self._lock:
			_logger.info(f'Writing guest token to {self._file}')
			with open(self._file, 'w') as fp:
				json.dump({'token': self.token, 'setTime': self.setTime}, fp)

	@property
	def token(self):
		if not self._token:
			self._read()
		return self._token

	@token.setter
	def token(self, token):
		super(type(self), type(self)).token.__set__(self, token)  # https://bugs.python.org/issue14965
		self._write()

	@property
	def setTime(self):
		self.token  # Implicitly reads from the file if necessary
		return self._setTime

	def reset(self):
		super().reset()
		with self._lock:
			_logger.info(f'Deleting guest token file {self._file}')
			try:
				os.remove(self._file)
			except FileNotFoundError:
				# Another process likely already removed the file
				pass


class _TwitterAPIType(enum.Enum):
	V2 = 0  # Introduced with the redesign
	GRAPHQL = 1


class _TwitterAPIScraper(snscrape.base.Scraper):
	def __init__(self, baseUrl, *, guestTokenManager = None, **kwargs):
		super().__init__(**kwargs)
		self._baseUrl = baseUrl
		if guestTokenManager is None:
			global _globalGuestTokenManager
			if _globalGuestTokenManager is None:
				_globalGuestTokenManager = GuestTokenManager()
			guestTokenManager = _globalGuestTokenManager
		self._guestTokenManager = guestTokenManager
		self._apiHeaders = {
			'User-Agent': None,
			'Authorization': _API_AUTHORIZATION_HEADER,
			'Referer': self._baseUrl,
			'Accept-Language': 'en-US,en;q=0.5',
		}
		self._set_random_user_agent()

	def _set_random_user_agent(self):
		self._userAgent = f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.{random.randint(0, 9999)} Safari/537.{random.randint(0, 99)}'
		self._apiHeaders['User-Agent'] = self._userAgent

	def _check_guest_token_response(self, r):
		if r.status_code != 200:
			self._set_random_user_agent()
			return False, f'non-200 response ({r.status_code})'
		return True, None

	def _ensure_guest_token(self, url = None):
		if self._guestTokenManager.token is None:
			_logger.info('Retrieving guest token')
			r = self._get(self._baseUrl if url is None else url, headers = {'User-Agent': self._userAgent}, responseOkCallback = self._check_guest_token_response)
			if (match := re.search(r'document\.cookie = decodeURIComponent\("gt=(\d+); Max-Age=10800; Domain=\.twitter\.com; Path=/; Secure"\);', r.text)):
				_logger.debug('Found guest token in HTML')
				self._guestTokenManager.token = match.group(1)
			if 'gt' in r.cookies:
				_logger.debug('Found guest token in cookies')
				self._guestTokenManager.token = r.cookies['gt']
			if not self._guestTokenManager.token:
				_logger.debug('No guest token in response')
				_logger.info('Retrieving guest token via API')
				r = self._post('https://api.twitter.com/1.1/guest/activate.json', data = b'', headers = self._apiHeaders, responseOkCallback = self._check_guest_token_response)
				o = r.json()
				if not o.get('guest_token'):
					raise snscrape.base.ScraperException('Unable to retrieve guest token')
				self._guestTokenManager.token = o['guest_token']
			assert self._guestTokenManager.token
		_logger.debug(f'Using guest token {self._guestTokenManager.token}')
		self._session.cookies.set('gt', self._guestTokenManager.token, domain = '.twitter.com', path = '/', secure = True, expires = self._guestTokenManager.setTime + _GUEST_TOKEN_VALIDITY)
		self._apiHeaders['x-guest-token'] = self._guestTokenManager.token

	def _unset_guest_token(self):
		self._guestTokenManager.reset()
		del self._session.cookies['gt']
		del self._apiHeaders['x-guest-token']

	def _check_api_response(self, r):
		if r.status_code in (403, 429):
			self._unset_guest_token()
			self._ensure_guest_token()
			return False, f'blocked ({r.status_code})'
		if r.headers.get('content-type', '').replace(' ', '') != 'application/json;charset=utf-8':
			return False, 'content type is not JSON'
		if r.status_code != 200:
			return False, 'non-200 status code'
		return True, None

	def _get_api_data(self, endpoint, apiType, params):
		self._ensure_guest_token()
		if apiType is _TwitterAPIType.GRAPHQL:
			params = urllib.parse.urlencode({'variables': json.dumps(params, separators = (',', ':'))}, quote_via = urllib.parse.quote)
		r = self._get(endpoint, params = params, headers = self._apiHeaders, responseOkCallback = self._check_api_response)
		try:
			obj = r.json()
		except json.JSONDecodeError as e:
			raise snscrape.base.ScraperException('Received invalid JSON from Twitter') from e
		return obj

	def _iter_api_data(self, endpoint, apiType, params, paginationParams = None, cursor = None, direction = _ScrollDirection.BOTTOM):
		# Iterate over endpoint with params/paginationParams, optionally starting from a cursor
		# Handles guest token extraction using the baseUrl passed to __init__ etc.
		# Order from params and paginationParams is preserved. To insert the cursor at a particular location, insert a 'cursor' key into paginationParams there (value is overwritten).
		# direction controls in which direction it should scroll from the initial response. BOTH equals TOP followed by BOTTOM.

		# Logic for dual scrolling: direction is set to top, but if the bottom cursor is found, bottomCursorAndStop is set accordingly.
		# Once the top pagination is exhausted, the bottomCursorAndStop is used and reset to None; it isn't set anymore after because the first entry condition will always be true for the bottom cursor.

		if cursor is None:
			reqParams = params
		else:
			reqParams = paginationParams.copy()
			reqParams['cursor'] = cursor
		bottomCursorAndStop = None
		if direction is _ScrollDirection.TOP or direction is _ScrollDirection.BOTH:
			dir = 'top'
		else:
			dir = 'bottom'
		stopOnEmptyResponse = False
		emptyResponsesOnCursor = 0
		while True:
			_logger.info(f'Retrieving scroll page {cursor}')
			obj = self._get_api_data(endpoint, apiType, reqParams)
			yield obj

			# No data format test, just a hard and loud crash if anything's wrong :-)
			newCursor = None
			promptCursor = None
			newBottomCursorAndStop = None
			if apiType is _TwitterAPIType.V2:
				instructions = obj['timeline']['instructions']
			elif apiType is _TwitterAPIType.GRAPHQL:
				if 'user' in obj['data']:
					# UserTweets, UserTweetsAndReplies
					instructions = obj['data']['user']['result']['timeline']['timeline']['instructions']
				else:
					# TweetDetail
					instructions = obj['data'].get('threaded_conversation_with_injections', {}).get('instructions', [])
			tweetCount = 0
			for instruction in instructions:
				if 'addEntries' in instruction:
					entries = instruction['addEntries']['entries']
				elif 'replaceEntry' in instruction:
					entries = [instruction['replaceEntry']['entry']]
				elif instruction.get('type') == 'TimelineAddEntries':
					entries = instruction['entries']
				else:
					continue
				tweetCount += self._count_tweets(entries)
				for entry in entries:
					if not (entry['entryId'].startswith('sq-cursor-') or entry['entryId'].startswith('cursor-')):
						continue
					if apiType is _TwitterAPIType.V2:
						entryCursor = entry['content']['operation']['cursor']['value']
						entryCursorStop = entry['content']['operation']['cursor'].get('stopOnEmptyResponse', None)
					elif apiType is _TwitterAPIType.GRAPHQL:
						cursorContent = entry['content']
						while cursorContent.get('itemType') == 'TimelineTimelineItem' or cursorContent.get('entryType') == 'TimelineTimelineItem':
							cursorContent = cursorContent['itemContent']
						entryCursor, entryCursorStop = cursorContent['value'], cursorContent.get('stopOnEmptyResponse', None)
					if entry['entryId'] == f'sq-cursor-{dir}' or entry['entryId'].startswith(f'cursor-{dir}-'):
						newCursor = entryCursor
						if entryCursorStop is not None:
							stopOnEmptyResponse = entryCursorStop
					elif entry['entryId'].startswith('cursor-showMoreThreadsPrompt-'): # E.g. 'offensive' replies button
						promptCursor = entryCursor
					elif direction is _ScrollDirection.BOTH and bottomCursorAndStop is None and (entry['entryId'] == 'sq-cursor-bottom' or entry['entryId'].startswith('cursor-bottom-')):
						newBottomCursorAndStop = (entryCursor, entryCursorStop or False)
			if bottomCursorAndStop is None and newBottomCursorAndStop is not None:
				bottomCursorAndStop = newBottomCursorAndStop
			if newCursor == cursor and tweetCount == 0:
				# Twitter sometimes returns the same cursor as requested and no results even though there are more results.
				# When this happens, retry the same cursor up to the retries setting.
				emptyResponsesOnCursor += 1
				if emptyResponsesOnCursor > self._retries:
					break
			if not newCursor or (stopOnEmptyResponse and tweetCount == 0):
				# End of pagination
				if promptCursor is not None:
					newCursor = promptCursor
				elif direction is _ScrollDirection.BOTH and bottomCursorAndStop is not None:
					dir = 'bottom'
					newCursor, stopOnEmptyResponse = bottomCursorAndStop
					bottomCursorAndStop = None
				else:
					break
			if newCursor != cursor:
				emptyResponsesOnCursor = 0
			cursor = newCursor
			reqParams = paginationParams.copy()
			reqParams['cursor'] = cursor

	def _count_tweets(self, entries):
		return sum(entry['entryId'].startswith('sq-I-t-') or entry['entryId'].startswith('tweet-') for entry in entries)

	def _v2_timeline_instructions_to_tweets(self, obj, includeConversationThreads = False):
		# No data format test, just a hard and loud crash if anything's wrong :-)
		for instruction in obj['timeline']['instructions']:
			if 'addEntries' in instruction:
				entries = instruction['addEntries']['entries']
			elif 'replaceEntry' in instruction:
				entries = [instruction['replaceEntry']['entry']]
			else:
				continue
			for entry in entries:
				if entry['entryId'].startswith('sq-I-t-') or entry['entryId'].startswith('tweet-'):
					yield from self._v2_instruction_tweet_entry_to_tweet(entry['entryId'], entry['content'], obj)
				elif includeConversationThreads and entry['entryId'].startswith('conversationThread-') and not entry['entryId'].endswith('-show_more_cursor'):
					for item in entry['content']['timelineModule']['items']:
						if item['entryId'].startswith('tweet-'):
							yield from self._v2_instruction_tweet_entry_to_tweet(item['entryId'], item, obj)

	def _v2_instruction_tweet_entry_to_tweet(self, entryId, entry, obj):
		if 'tweet' in entry['item']['content']:
			if 'promotedMetadata' in entry['item']['content']['tweet']: # Promoted tweet aka ads
				return
			if entry['item']['content']['tweet']['id'] not in obj['globalObjects']['tweets']:
				_logger.warning(f'Skipping tweet {entry["item"]["content"]["tweet"]["id"]} which is not in globalObjects')
				return
			tweet = obj['globalObjects']['tweets'][entry['item']['content']['tweet']['id']]
		elif 'tombstone' in entry['item']['content']:
			if 'tweet' not in entry['item']['content']['tombstone']: # E.g. deleted reply
				return
			if entry['item']['content']['tombstone']['tweet']['id'] not in obj['globalObjects']['tweets']:
				_logger.warning(f'Skipping tweet {entry["item"]["content"]["tombstone"]["tweet"]["id"]} which is not in globalObjects')
				return
			tweet = obj['globalObjects']['tweets'][entry['item']['content']['tombstone']['tweet']['id']]
		else:
			raise snscrape.base.ScraperException(f'Unable to handle entry {entryId!r}')
		yield self._tweet_to_tweet(tweet, obj)

	def _get_tweet_id(self, tweet):
		return tweet['id'] if 'id' in tweet else int(tweet['id_str'])

	def _make_tweet(self, tweet, user, retweetedTweet = None, quotedTweet = None, card = None):
		tweetId = self._get_tweet_id(tweet)
		kwargs = {}
		kwargs['id'] = tweetId
		kwargs['rawContent'] = tweet['full_text']
		kwargs['renderedContent'] = self._render_text_with_urls(tweet['full_text'], tweet['entities'].get('urls'))
		kwargs['user'] = user
		kwargs['date'] = email.utils.parsedate_to_datetime(tweet['created_at'])
		if tweet['entities'].get('urls'):
			kwargs['links'] = [TextLink(
			                     text = u.get('display_url'),
			                     url = u['expanded_url'],
			                     tcourl = u['url'],
			                     indices = tuple(u['indices']),
			                   ) for u in tweet['entities']['urls']]
		kwargs['url'] = f'https://twitter.com/{user.username}/status/{tweetId}'
		kwargs['replyCount'] = tweet['reply_count']
		kwargs['retweetCount'] = tweet['retweet_count']
		kwargs['likeCount'] = tweet['favorite_count']
		kwargs['quoteCount'] = tweet['quote_count']
		kwargs['conversationId'] = tweet['conversation_id'] if 'conversation_id' in tweet else int(tweet['conversation_id_str'])
		kwargs['lang'] = tweet['lang']
		kwargs['source'] = tweet['source']
		if (match := re.search(r'href=[\'"]?([^\'" >]+)', tweet['source'])):
			kwargs['sourceUrl'] = match.group(1)
		if (match := re.search(r'>([^<]*)<', tweet['source'])):
			kwargs['sourceLabel'] = match.group(1)
		if 'extended_entities' in tweet and 'media' in tweet['extended_entities']:
			media = []
			for medium in tweet['extended_entities']['media']:
				if (mediumO := self._make_medium(medium, tweetId)):
					media.append(mediumO)
			if media:
				kwargs['media'] = media
		if retweetedTweet:
			kwargs['retweetedTweet'] = retweetedTweet
		if quotedTweet:
			kwargs['quotedTweet'] = quotedTweet
		if (inReplyToTweetId := tweet.get('in_reply_to_status_id_str')):
			kwargs['inReplyToTweetId'] = int(inReplyToTweetId)
			inReplyToUserId = int(tweet['in_reply_to_user_id_str'])
			if inReplyToUserId == kwargs['user'].id:
				kwargs['inReplyToUser'] = kwargs['user']
			elif tweet['entities'].get('user_mentions'):
				for u in tweet['entities']['user_mentions']:
					if u['id_str'] == tweet['in_reply_to_user_id_str']:
						kwargs['inReplyToUser'] = User(username = u['screen_name'], id = u['id'] if 'id' in u else int(u['id_str']), displayname = u['name'])
			if 'inReplyToUser' not in kwargs:
				kwargs['inReplyToUser'] = User(username = tweet['in_reply_to_screen_name'], id = inReplyToUserId)
		if tweet['entities'].get('user_mentions'):
			kwargs['mentionedUsers'] = [User(username = u['screen_name'], id = u['id'] if 'id' in u else int(u['id_str']), displayname = u['name']) for u in tweet['entities']['user_mentions']]

		# https://developer.twitter.com/en/docs/tutorials/filtering-tweets-by-location
		if tweet.get('coordinates'):
			# coordinates root key (if present) presents coordinates in the form [LONGITUDE, LATITUDE]
			if (coords := tweet['coordinates']['coordinates']) and len(coords) == 2:
				kwargs['coordinates'] = Coordinates(coords[0], coords[1])
		elif tweet.get('geo'):
			# coordinates root key (if present) presents coordinates in the form [LATITUDE, LONGITUDE]
			if (coords := tweet['geo']['coordinates']) and len(coords) == 2:
				kwargs['coordinates'] = Coordinates(coords[1], coords[0])
		if tweet.get('place'):
			kwargs['place'] = Place(tweet['place']['full_name'], tweet['place']['name'], tweet['place']['place_type'], tweet['place']['country'], tweet['place']['country_code'])
			if 'coordinates' not in kwargs and tweet['place'].get('bounding_box') and (coords := tweet['place']['bounding_box']['coordinates']) and coords[0] and len(coords[0][0]) == 2:
				# Take the first (longitude, latitude) couple of the "place square"
				kwargs['coordinates'] = Coordinates(coords[0][0][0], coords[0][0][1])
		if tweet['entities'].get('hashtags'):
			kwargs['hashtags'] = [o['text'] for o in tweet['entities']['hashtags']]
		if tweet['entities'].get('symbols'):
			kwargs['cashtags'] = [o['text'] for o in tweet['entities']['symbols']]
		if card:
			kwargs['card'] = card
			if hasattr(card, 'url') and '//t.co/' in card.url:
				# Try to convert the URL to the non-shortened/t.co one
				# Retweets inherit the card but not the outlinks; try to get them from the retweeted tweet instead in that case.
				candidates = []
				if 'links' in kwargs:
					candidates.extend(kwargs['links'])
				if retweetedTweet:
					candidates.extend(retweetedTweet.links)
				for u in candidates:
					if u.tcourl == card.url:
						card.url = u.url
						break
				else:
					_logger.warning(f'Could not translate t.co card URL on tweet {tweetId}')
		return Tweet(**kwargs)

	def _make_medium(self, medium, tweetId):
		if medium['type'] == 'photo':
			if '?format=' in medium['media_url_https'] or '&format=' in medium['media_url_https']:
				return Photo(previewUrl = medium['media_url_https'], fullUrl = medium['media_url_https'])
			if '.' not in medium['media_url_https']:
				_logger.warning(f'Skipping malformed medium URL on tweet {tweetId}: {medium["media_url_https"]!r} contains no dot')
				return
			baseUrl, format = medium['media_url_https'].rsplit('.', 1)
			if format not in ('jpg', 'png'):
				_logger.warning(f'Skipping photo with unknown format on tweet {tweetId}: {format!r}')
				return
			return Photo(
				previewUrl = f'{baseUrl}?format={format}&name=small',
				fullUrl = f'{baseUrl}?format={format}&name=large',
			)
		elif medium['type'] == 'video' or medium['type'] == 'animated_gif':
			variants = []
			for variant in medium['video_info']['variants']:
				variants.append(VideoVariant(contentType = variant['content_type'], url = variant['url'], bitrate = variant.get('bitrate')))
			mKwargs = {
				'thumbnailUrl': medium['media_url_https'],
				'variants': variants,
			}
			if medium['type'] == 'video':
				mKwargs['duration'] = medium['video_info']['duration_millis'] / 1000
				if (ext := medium.get('ext')) and (mediaStats := ext.get('mediaStats')) and isinstance(r := mediaStats['r'], dict) and 'ok' in r and isinstance(r['ok'], dict):
					mKwargs['views'] = int(r['ok']['viewCount'])
				elif (mediaStats := medium.get('mediaStats')):
					mKwargs['views'] = mediaStats['viewCount']
				cls = Video
			elif medium['type'] == 'animated_gif':
				cls = Gif
			return cls(**mKwargs)
		else:
			_logger.warning(f'Unsupported medium type on tweet {tweetId}: {medium["type"]!r}')

	def _make_card(self, card, apiType, tweetId):
		bindingValues = {}

		def _kwargs_from_map(keyKwargMap):
			nonlocal bindingValues
			return {kwarg: bindingValues[key] for key, kwarg in keyKwargMap.items() if key in bindingValues}

		userRefs = {}
		if apiType is _TwitterAPIType.V2:
			for o in card.get('users', {}).values():
				userId = o['id']
				assert userId not in userRefs
				userRefs[userId] = self._user_to_user(o)
		elif apiType is _TwitterAPIType.GRAPHQL:
			for o in card['legacy'].get('user_refs', {}):
				userId = int(o['rest_id'])
				if userId in userRefs:
					_logger.warning(f'Duplicate user {userId} in card on tweet {tweetId}')
					continue
				if 'legacy' in o:
					userRefs[userId] = self._user_to_user(o['legacy'], id_ = userId)
				else:
					userRefs[userId] = UserRef(id = userId)

		if apiType is _TwitterAPIType.V2:
			messyBindingValues = card['binding_values'].items()
		elif apiType is _TwitterAPIType.GRAPHQL:
			messyBindingValues = ((x['key'], x['value']) for x in card['legacy']['binding_values'])
		for key, value in messyBindingValues:
			if 'type' not in value:
				# Silently ignore creator/site entries since they frequently appear like this.
				if key not in ('creator', 'site'):
					_logger.warning(f'Skipping type-less card value {key!r} on tweet {tweetId}')
				continue
			if value['type'] == 'STRING':
				bindingValues[key] = value['string_value']
				if key.endswith('_datetime_utc'):
					bindingValues[key] = datetime.datetime.strptime(bindingValues[key], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo = datetime.timezone.utc)
			elif value['type'] == 'IMAGE':
				bindingValues[key] = value['image_value']['url']
			elif value['type'] == 'IMAGE_COLOR':
				# Silently discard this.
				pass
			elif value['type'] == 'BOOLEAN':
				bindingValues[key] = value['boolean_value']
			elif value['type'] == 'USER':
				bindingValues[key] = userRefs[int(value['user_value']['id_str'])]
			else:
				_logger.warning(f'Unsupported card value type on {key!r} on tweet {tweetId}: {value["type"]!r}')

		if apiType is _TwitterAPIType.V2:
			cardName = card['name']
		elif apiType is _TwitterAPIType.GRAPHQL:
			cardName = card['legacy']['name']

		if cardName in ('summary', 'summary_large_image', 'app', 'direct_store_link_app'):
			keyKwargMap = {
				'title': 'title',
				'description': 'description',
				'card_url': 'url',
				'site': 'siteUser',
				'creator': 'creatorUser',
			}
			if cardName in ('app', 'direct_store_link_app'):
				keyKwargMap['thumbnail_original'] = 'thumbnailUrl'
				return AppCard(**_kwargs_from_map(keyKwargMap))
			else:
				keyKwargMap['thumbnail_image_original'] = 'thumbnailUrl'
				return SummaryCard(**_kwargs_from_map(keyKwargMap))
		elif any(cardName.startswith(x) for x in ('poll2choice_', 'poll3choice_', 'poll4choice_')) and cardName.split('_', 1)[1] in ('text_only', 'image', 'video'):
			kwargs = _kwargs_from_map({'end_datetime_utc': 'endDate', 'last_updated_datetime_utc': 'lastUpdateDate', 'duration_minutes': 'duration', 'counts_are_final': 'finalResults'})

			options = []
			for key in sorted(bindingValues):
				if key.startswith('choice') and key.endswith('_label'):
					optKwargs = {'label': bindingValues[key]}
					if (count := bindingValues.get(f'{key[:-5]}count')):
						optKwargs['count'] = int(count)
					options.append(PollOption(**optKwargs))
			kwargs['options'] = options
			kwargs['duration'] = int(kwargs['duration'])

			if cardName.endswith('_image'):
				kwargs['medium'] = Photo(previewUrl = bindingValues['image_small'], fullUrl = bindingValues['image_original'])
			elif cardName.endswith('_video'):
				variants = []
				variants.append(VideoVariant(contentType = 'application/x-mpegurl', url = bindingValues['player_hls_url'], bitrate = None))
				if 'vmap' not in bindingValues['player_stream_url']:
					_logger.warning(f'Non-VMAP URL in {cardName} player_stream_url on tweet {tweetId}')
				variants.append(VideoVariant(contentType = 'text/xml', url = bindingValues['player_stream_url'], bitrate = None))
				kwargs['medium'] = Video(thumbnailUrl = bindingValues['player_image_original'], variants = variants, duration = int(bindingValues['content_duration_seconds']))

			return PollCard(**kwargs)
		elif cardName == 'player':
			return PlayerCard(**_kwargs_from_map({'title': 'title', 'description': 'description', 'card_url': 'url', 'player_image_original': 'imageUrl', 'site': 'siteUser'}))
		elif cardName in ('promo_image_convo', 'promo_video_convo'):
			kwargs = _kwargs_from_map({'thank_you_text': 'thankYouText', 'thank_you_url': 'thankYouUrl', 'thank_you_shortened_url': 'thankYouTcoUrl'})
			kwargs['actions'] = []
			for l in ('one', 'two', 'three', 'four'):
				if f'cta_{l}' in bindingValues:
					kwargs['actions'].append(PromoConvoAction(label = bindingValues[f'cta_{l}'], tweet = bindingValues[f'cta_{l}_tweet']))
			if 'image' in cardName:
				kwargs['medium'] = Photo(previewUrl = bindingValues['promo_image_small'], fullUrl = bindingValues['promo_image_original'])
				if 'cover_promo_image' in bindingValues:
					kwargs['cover'] = Photo(previewUrl = bindingValues['cover_promo_image_small'], fullUrl = bindingValues['cover_promo_image_original'])
			elif 'video' in cardName:
				variants = []
				variants.append(VideoVariant(contentType = bindingValues['player_stream_content_type'], url = bindingValues['player_stream_url'], bitrate = None))
				if bindingValues['player_stream_url'] != bindingValues['player_url']:
					if 'vmap' not in bindingValues['player_url']:
						_logger.warning(f'Non-VMAP URL in {cardName} player_url on tweet {tweetId}')
					variants.append(VideoVariant(contentType = 'text/xml', url = bindingValues['player_url'], bitrate = None))
				kwargs['medium'] = Video(thumbnailUrl = bindingValues['player_image_original'], variants = variants, duration = int(bindingValues['content_duration_seconds']))
			return PromoConvoCard(**kwargs)
		elif cardName in ('745291183405076480:broadcast', '3691233323:periscope_broadcast'):
			keyKwargMap = {'broadcast_state': 'state', 'broadcast_source': 'source', 'site': 'siteUser'}
			if cardName == '745291183405076480:broadcast':
				keyKwargMap = {**keyKwargMap, 'broadcast_id': 'id', 'broadcast_url': 'url', 'broadcast_title': 'title', 'broadcast_thumbnail_original': 'thumbnailUrl'}
			else:
				keyKwargMap = {**keyKwargMap, 'id': 'id', 'url': 'url', 'title': 'title', 'description': 'description', 'total_participants': 'totalParticipants', 'full_size_thumbnail_url': 'thumbnailUrl'}
			kwargs = _kwargs_from_map(keyKwargMap)
			if 'broadcaster_twitter_id' in bindingValues:
				kwargs['broadcaster'] = User(id = int(bindingValues['broadcaster_twitter_id']), username = bindingValues['broadcaster_username'], displayname = bindingValues['broadcaster_display_name'])
			if 'siteUser' not in kwargs:
				kwargs['siteUser'] = None
			if cardName == '745291183405076480:broadcast':
				return BroadcastCard(**kwargs)
			else:
				kwargs['totalParticipants'] = int(kwargs['totalParticipants'])
				return PeriscopeBroadcastCard(**kwargs)
		elif cardName == '745291183405076480:live_event':
			kwargs = _kwargs_from_map({'event_id': 'id', 'event_title': 'title', 'event_category': 'category', 'event_subtitle': 'description'})
			kwargs['id'] = int(kwargs['id'])
			kwargs['photo'] = Photo(previewUrl = bindingValues['event_thumbnail_small'], fullUrl = bindingValues.get('event_thumbnail_original') or bindingValues['event_thumbnail'])
			return EventCard(event = Event(**kwargs))
		elif cardName == '3337203208:newsletter_publication':
			kwargs = _kwargs_from_map({'newsletter_title': 'title', 'newsletter_description': 'description', 'newsletter_image_original': 'imageUrl', 'card_url': 'url', 'revue_account_id': 'revueAccountId', 'issue_count': 'issueCount'})
			kwargs['revueAccountId'] = int(kwargs['revueAccountId'])
			kwargs['issueCount'] = int(kwargs['issueCount'])
			return NewsletterCard(**kwargs)
		elif cardName == '3337203208:newsletter_issue':
			kwargs = _kwargs_from_map({
				'newsletter_title': 'newsletterTitle',
				'newsletter_description': 'newsletterDescription',
				'issue_title': 'issueTitle',
				'issue_description': 'issueDescription',
				'issue_number': 'issueNumber',
				'issue_image_original': 'imageUrl',
				'card_url': 'url',
				'revue_account_id': 'revueAccountId'
			})
			kwargs['issueNumber'] = int(kwargs['issueNumber'])
			kwargs['revueAccountId'] = int(kwargs['revueAccountId'])
			return NewsletterIssueCard(**kwargs)
		elif cardName == 'amplify':
			return AmplifyCard(
				id = bindingValues['amplify_content_id'],
				video = Video(
					thumbnailUrl = bindingValues['player_image'],
					variants = [VideoVariant(contentType = bindingValues['player_stream_content_type'], url = bindingValues['amplify_url_vmap'], bitrate = None)],
				),
			)
		elif cardName == 'appplayer':
			kwargs = _kwargs_from_map({'title': 'title', 'app_category': 'appCategory', 'player_owner_id': 'playerOwnerId', 'site': 'siteUser'})
			kwargs['playerOwnerId'] = int(kwargs['playerOwnerId'])
			variants = []
			variants.append(VideoVariant(contentType = 'application/x-mpegurl', url = bindingValues['player_hls_url'], bitrate = None))
			if 'vmap' not in bindingValues['player_url']:
				_logger.warning(f'Non-VMAP URL in {cardName} player_url on tweet {tweetId}')
			variants.append(VideoVariant(contentType = 'text/xml', url = bindingValues['player_url'], bitrate = None))
			kwargs['video'] = Video(thumbnailUrl = bindingValues['player_image_original'], variants = variants, duration = int(bindingValues['content_duration_seconds']))
			return AppPlayerCard(**kwargs)
		elif cardName == '3691233323:audiospace':
			return SpacesCard(**_kwargs_from_map({'card_url': 'url', 'id': 'id'}))
		elif cardName == '2586390716:message_me':
			# Note that the strings in Twitter's JS appear to have an incorrect mapping that then gets changed somewhere in the 1.8 MiB of JS!
			# cta_1, 3, and 4 should mean 'Message us', 'Send a private message', and 'Send me a private message', but the correct mapping is currently unknown.
			ctas = {'message_me_card_cta_2': 'Send us a private message'}
			if bindingValues['cta'] not in ctas:
				_logger.warning(f'Unsupported message_me card cta on tweet {tweetId}: {bindingValues["cta"]!r}')
				return
			return MessageMeCard(**_kwargs_from_map({'recipient': 'recipient', 'card_url': 'url'}), buttonText = ctas[bindingValues['cta']])
		elif cardName == 'unified_card':
			o = json.loads(bindingValues['unified_card'])
			kwargs = {}
			if 'type' in o:
				unifiedCardType = o.get('type')
				if unifiedCardType not in (
					'image_app',
					'image_carousel_app',
					'image_carousel_website',
					'image_multi_dest_carousel_website',
					'image_website',
					'mixed_media_multi_dest_carousel_website',
					'mixed_media_single_dest_carousel_app',
					'mixed_media_single_dest_carousel_website',
					'video_app',
					'video_carousel_app',
					'video_carousel_website',
					'video_multi_dest_carousel_website',
					'video_website',
				):
					_logger.warning(f'Unsupported unified_card type on tweet {tweetId}: {unifiedCardType!r}')
					return
				kwargs['type'] = unifiedCardType
			elif set(c['type'] for c in o['component_objects'].values()) not in ({'media', 'twitter_list_details'}, {'media', 'community_details'}):
				_logger.warning(f'Unsupported unified_card type on tweet {tweetId}')
				return

			kwargs['componentObjects'] = {}
			for k, v in o['component_objects'].items():
				if v['type'] == 'details':
					co = UnifiedCardDetailComponentObject(content = v['data']['title']['content'], destinationKey = v['data']['destination'])
				elif v['type'] == 'media':
					co = UnifiedCardMediumComponentObject(mediumKey = v['data']['id'], destinationKey = v['data']['destination'])
				elif v['type'] == 'button_group':
					if not all(b['type'] == 'cta' for b in v['data']['buttons']):
						_logger.warning(f'Unsupported unified_card button_group button type on tweet {tweetId}')
						return
					buttons = [UnifiedCardButton(text = b['action'][0].upper() + re.sub('[A-Z]', lambda x: f' {x[0]}', b['action'][1:]), destinationKey = b['destination']) for b in v['data']['buttons']]
					co = UnifiedCardButtonGroupComponentObject(buttons = buttons)
				elif v['type'] == 'swipeable_media':
					media = [UnifiedCardSwipeableMediaMedium(mediumKey = m['id'], destinationKey = m['destination']) for m in v['data']['media_list']]
					co = UnifiedCardSwipeableMediaComponentObject(media = media)
				elif v['type'] == 'app_store_details':
					co = UnifiedCardAppStoreComponentObject(appKey = v['data']['app_id'], destinationKey = v['data']['destination'])
				elif v['type'] == 'twitter_list_details':
					co = UnifiedCardTwitterListDetailsComponentObject(
						name = v['data']['name']['content'],
						memberCount = v['data']['member_count'],
						subscriberCount = v['data']['subscriber_count'],
						user = self._user_to_user(o['users'][v['data']['user_id']]),
						destinationKey = v['data']['destination'],
					)
				elif v['type'] == 'community_details':
					co = UnifiedCardTwitterCommunityDetailsComponentObject(
						name = v['data']['name']['content'],
						theme = v['data']['theme'],
						membersCount = v['data']['member_count'],
						destinationKey = v['data']['destination'],
						membersFacepile = [self._user_to_user(u) for u in map(o['users'].get, v['data']['members_facepile']) if u],
					)
				else:
					_logger.warning(f'Unsupported unified_card component type on tweet {tweetId}: {v["type"]!r}')
					return
				kwargs['componentObjects'][k] = co

			kwargs['destinations'] = {}
			for k, v in o['destination_objects'].items():
				dKwargs = {}
				if 'url_data' in v['data']:
					dKwargs['url'] = v['data']['url_data']['url']
				if 'app_id' in v['data']:
					dKwargs['appKey'] = v['data']['app_id']
				if 'media_id' in v['data']:
					dKwargs['mediumKey'] = v['data']['media_id']
				kwargs['destinations'][k] = UnifiedCardDestination(**dKwargs)

			kwargs['media'] = {}
			for k, v in o['media_entities'].items():
				if (medium := self._make_medium(v, tweetId)):
					kwargs['media'][k] = medium

			if 'app_store_data' in o:
				kwargs['apps'] = {}
				for k, v in o['app_store_data'].items():
					variants = []
					for var in v:
						vKwargsMap = {
							'type': 'type',
							'id': 'id',
							'icon_media_key': 'iconMediumKey',
							'country_code': 'countryCode',
							'num_installs': 'installs',
							'size_bytes': 'size',
							'is_free': 'isFree',
							'is_editors_choice': 'isEditorsChoice',
							'has_in_app_purchases': 'hasInAppPurchases',
							'has_in_app_ads': 'hasInAppAds',
						}
						vKwargs = {kwarg: var[key] for key, kwarg in vKwargsMap.items() if key in var}
						vKwargs['title'] = var['title']['content']
						if 'description' in var:
							vKwargs['description'] = var['description']['content']
						vKwargs['category'] = var['category']['content']
						if (ratings := var['ratings']):
							vKwargs['ratingAverage'] = var['ratings']['star']
							vKwargs['ratingCount'] = var['ratings']['count']
						vKwargs['url'] = f'https://play.google.com/store/apps/details?id={var["id"]}' if var['type'] == 'android_app' else f'https://itunes.apple.com/app/id{var["id"]}'
						if 'iconMediumKey' in vKwargs and vKwargs['iconMediumKey'] not in kwargs['media']:
							# https://github.com/JustAnotherArchivist/snscrape/issues/470
							_logger.warning(f'Tweet {tweetId} contains an app icon medium key {vKwargs["iconMediumKey"]!r} on app {vKwargs["type"]!r}/{vKwargs["id"]!r}, but the corresponding medium is missing; dropping')
							del vKwargs['iconMediumKey']
						variants.append(UnifiedCardApp(**vKwargs))
					kwargs['apps'][k] = variants

			if o['components']:
				kwargs['components'] = o['components']

			if 'layout' in o:
				if o['layout']['type'] != 'swipeable':
					_logger.warning(f'Unsupported unified_card layout type on tweet {tweetId}: {o["layout"]["type"]!r}')
					return
				kwargs['swipeableLayoutSlides'] = [UnifiedCardSwipeableLayoutSlide(mediumComponentKey = v[0], componentKey = v[1]) for v in o['layout']['data']['slides']]

			return UnifiedCard(**kwargs)

		_logger.warning(f'Unsupported card type on tweet {tweetId}: {cardName!r}')

	def _tweet_to_tweet(self, tweet, obj):
		user = self._user_to_user(obj['globalObjects']['users'][tweet['user_id_str']])
		kwargs = {}
		if 'retweeted_status_id_str' in tweet:
			kwargs['retweetedTweet'] = self._tweet_to_tweet(obj['globalObjects']['tweets'][tweet['retweeted_status_id_str']], obj)
		if 'quoted_status_id_str' in tweet and tweet['quoted_status_id_str'] in obj['globalObjects']['tweets']:
			kwargs['quotedTweet'] = self._tweet_to_tweet(obj['globalObjects']['tweets'][tweet['quoted_status_id_str']], obj)
		if 'card' in tweet:
			kwargs['card'] = self._make_card(tweet['card'], _TwitterAPIType.V2, self._get_tweet_id(tweet))
		return self._make_tweet(tweet, user, **kwargs)

	def _graphql_timeline_tweet_item_result_to_tweet(self, result):
		if result['__typename'] == 'Tweet':
			pass
		elif result['__typename'] == 'TweetWithVisibilityResults':
			#TODO Include result['softInterventionPivot'] in the Tweet object
			result = result['tweet']
		else:
			raise snscrape.base.ScraperException(f'Unknown result type {result["__typename"]!r}')
		tweet = result['legacy']
		userId = int(result['core']['user_results']['result']['rest_id'])
		user = self._user_to_user(result['core']['user_results']['result']['legacy'], id_ = userId)
		kwargs = {}
		if 'retweeted_status_result' in tweet:
			kwargs['retweetedTweet'] = self._graphql_timeline_tweet_item_result_to_tweet(tweet['retweeted_status_result']['result'])
		if 'quoted_status_result' in result:
			if result['quoted_status_result']['result']['__typename'] == 'TweetTombstone':
				kwargs['quotedTweet'] = TweetRef(id = int(tweet['quoted_status_id_str']))
			else:
				kwargs['quotedTweet'] = self._graphql_timeline_tweet_item_result_to_tweet(result['quoted_status_result']['result'])
		elif 'quotedRefResult' in result:
			if result['quotedRefResult']['result']['__typename'] == 'TweetTombstone':
				kwargs['quotedTweet'] = TweetRef(id = int(tweet['quoted_status_id_str']))
			else:
				kwargs['quotedTweet'] = TweetRef(id = int(result['quotedRefResult']['result']['rest_id']))
		elif 'quoted_status_id_str' in tweet:
			kwargs['quotedTweet'] = TweetRef(id = int(tweet['quoted_status_id_str']))
		if 'card' in result:
			kwargs['card'] = self._make_card(result['card'], _TwitterAPIType.GRAPHQL, self._get_tweet_id(tweet))
		return self._make_tweet(tweet, user, **kwargs)

	def _graphql_timeline_instructions_to_tweets(self, instructions, includeConversationThreads = False):
		for instruction in instructions:
			if instruction['type'] != 'TimelineAddEntries':
				continue
			for entry in instruction['entries']:
				if entry['entryId'].startswith('tweet-'):
					if entry['content']['entryType'] == 'TimelineTimelineItem' and entry['content']['itemContent']['itemType'] == 'TimelineTweet':
						yield self._graphql_timeline_tweet_item_result_to_tweet(entry['content']['itemContent']['tweet_results']['result'])
					else:
						logger.warning('Got unrecognised timeline tweet item(s)')
				elif includeConversationThreads and entry['entryId'].startswith('conversationthread-'):  #TODO show more cursor?
					for item in entry['content']['items']:
						if item['entryId'].startswith(f'{entry["entryId"]}-tweet-'):
							yield self._graphql_timeline_tweet_item_result_to_tweet(item['item']['itemContent']['tweet_results']['result'])

	def _render_text_with_urls(self, text, urls):
		if not urls:
			return text
		out = []
		out.append(text[:urls[0]['indices'][0]])
		urlsSorted = sorted(urls, key = lambda x: x['indices'][0]) # Ensure that they're in left to right appearance order
		assert all(url['indices'][1] <= nextUrl['indices'][0] for url, nextUrl in zip(urls, urls[1:])), 'broken URL indices'
		for url, nextUrl in itertools.zip_longest(urls, urls[1:]):
			if 'display_url' in url:
				out.append(url['display_url'])
			out.append(text[url['indices'][1] : nextUrl['indices'][0] if nextUrl is not None else None])
		return ''.join(out)

	def _user_to_user(self, user, id_ = None):
		kwargs = {}
		kwargs['username'] = user['screen_name']
		kwargs['id'] = id_ if id_ else user['id'] if 'id' in user else int(user['id_str'])
		kwargs['displayname'] = user['name']
		kwargs['rawDescription'] = user['description']
		kwargs['renderedDescription'] = self._render_text_with_urls(user['description'], user['entities']['description'].get('urls'))
		if user['entities']['description'].get('urls'):
			kwargs['descriptionLinks'] = [TextLink(
			                                text = x.get('display_url'),
			                                url = x['expanded_url'],
			                                tcourl = x['url'],
			                                indices = tuple(x['indices']),
			                              ) for x in user['entities']['description']['urls']]
		kwargs['verified'] = user.get('verified')
		kwargs['created'] = email.utils.parsedate_to_datetime(user['created_at'])
		kwargs['followersCount'] = user['followers_count']
		kwargs['friendsCount'] = user['friends_count']
		kwargs['statusesCount'] = user['statuses_count']
		kwargs['favouritesCount'] = user['favourites_count']
		kwargs['listedCount'] = user['listed_count']
		kwargs['mediaCount'] = user['media_count']
		kwargs['location'] = user['location']
		kwargs['protected'] = user.get('protected')
		if user.get('url'):
			entity = user['entities'].get('url', {}).get('urls', [None])[0]
			if not entity or entity['url'] != user['url']:
				self.logger.warning(f'Link inconsistency on user {kwargs["id"]}')
			if not entity:
				entity = {'indices': (0, len(user['url']))}
			kwargs['link'] = TextLink(text = entity.get('display_url'), url = entity.get('expanded_url', user['url']), tcourl = user['url'], indices = tuple(entity['indices']))
		kwargs['profileImageUrl'] = user['profile_image_url_https']
		kwargs['profileBannerUrl'] = user.get('profile_banner_url')
		if 'ext' in user and (label := user['ext']['highlightedLabel']['r']['ok'].get('label')):
			kwargs['label'] = self._user_label_to_user_label(label)
		return User(**kwargs)

	def _user_label_to_user_label(self, label):
		labelKwargs = {}
		labelKwargs['description'] = label['description']
		if 'url' in label and 'url' in label['url']:
			labelKwargs['url'] = label['url']['url']
		if 'badge' in label and 'url' in label['badge']:
			labelKwargs['badgeUrl'] = label['badge']['url']
		if 'longDescription' in label and 'text' in label['longDescription']:
			labelKwargs['longDescription'] = label['longDescription']['text']
		return UserLabel(**labelKwargs)

	@classmethod
	def _cli_construct(cls, argparseArgs, *args, **kwargs):
		kwargs['guestTokenManager'] = _CLIGuestTokenManager()
		return super()._cli_construct(argparseArgs, *args, **kwargs)


class TwitterSearchScraper(_TwitterAPIScraper):
	name = 'twitter-search'

	def __init__(self, query, *, cursor = None, top = False, **kwargs):
		if not query.strip():
			raise ValueError('empty query')
		super().__init__(baseUrl = 'https://twitter.com/search?' + urllib.parse.urlencode({'f': 'live', 'lang': 'en', 'q': query, 'src': 'spelling_expansion_revert_click'}), **kwargs)
		self._query = query  # Note: may get replaced by subclasses when using user ID resolution
		self._cursor = cursor
		self._top = top

	def _check_scroll_response(self, r):
		if r.status_code == 429:
			# Accept a 429 response as "valid" to prevent retries; handled explicitly in get_items
			return True, None
		if r.headers.get('content-type').replace(' ', '') != 'application/json;charset=utf-8':
			return False, 'content type is not JSON'
		if r.status_code != 200:
			return False, 'non-200 status code'
		return True, None

	def get_items(self):
		if not self._query.strip():
			raise ValueError('empty query')
		paginationParams = {
			'include_profile_interstitial_type': '1',
			'include_blocking': '1',
			'include_blocked_by': '1',
			'include_followed_by': '1',
			'include_want_retweets': '1',
			'include_mute_edge': '1',
			'include_can_dm': '1',
			'include_can_media_tag': '1',
			'include_ext_has_nft_avatar': '1',
			'skip_status': '1',
			'cards_platform': 'Web-12',
			'include_cards': '1',
			'include_ext_alt_text': 'true',
			'include_quote_count': 'true',
			'include_reply_count': '1',
			'tweet_mode': 'extended',
			'include_entities': 'true',
			'include_user_entities': 'true',
			'include_ext_media_color': 'true',
			'include_ext_media_availability': 'true',
			'include_ext_sensitive_media_warning': 'true',
			'include_ext_trusted_friends_metadata': 'true',
			'send_error_codes': 'true',
			'simple_quoted_tweet': 'true',
			'q': self._query,
			'tweet_search_mode': 'live',
			'count': '20',
			'query_source': 'spelling_expansion_revert_click',
			'cursor': None,
			'pc': '1',
			'spelling_corrections': '1',
			'ext': 'mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,enrichments,superFollowMetadata,unmentionInfo',
		}
		params = paginationParams.copy()
		del params['cursor']

		if self._top:
			del params['tweet_search_mode']
			del paginationParams['tweet_search_mode']

		for obj in self._iter_api_data('https://api.twitter.com/2/search/adaptive.json', _TwitterAPIType.V2, params, paginationParams, cursor = self._cursor):
			yield from self._v2_timeline_instructions_to_tweets(obj)

	@classmethod
	def _cli_setup_parser(cls, subparser):
		subparser.add_argument('--cursor', metavar = 'CURSOR')
		subparser.add_argument('--top', action = 'store_true', default = False, help = 'Enable fetching top tweets instead of live/chronological')
		subparser.add_argument('query', type = snscrape.base.nonempty_string('query'), help = 'A Twitter search string')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, args.query, cursor = args.cursor, top = args.top)


class TwitterUserScraper(TwitterSearchScraper):
	name = 'twitter-user'

	def __init__(self, user, **kwargs):
		self._isUserId = isinstance(user, int)
		if not self._isUserId and not self.is_valid_username(user):
			raise ValueError('Invalid username')
		super().__init__(f'from:{user}', **kwargs)
		self._user = user
		self._baseUrl = f'https://twitter.com/{self._user}' if not self._isUserId else f'https://twitter.com/i/user/{self._user}'

	def _get_entity(self):
		self._ensure_guest_token()
		if not self._isUserId:
			fieldName = 'screen_name'
			endpoint = 'https://twitter.com/i/api/graphql/7mjxD3-C6BxitPMVQ6w0-Q/UserByScreenName'
		else:
			fieldName = 'userId'
			endpoint = 'https://twitter.com/i/api/graphql/I5nvpI91ljifos1Y3Lltyg/UserByRestId'
		variables = {fieldName: str(self._user), 'withSafetyModeUserFields': True, 'withSuperFollowsUserFields': True}
		obj = self._get_api_data(endpoint, _TwitterAPIType.GRAPHQL, params = variables)
		if not obj['data'] or obj['data']['user']['result']['__typename'] == 'UserUnavailable':
			return None
		user = obj['data']['user']['result']
		rawDescription = user['legacy']['description']
		renderedDescription = self._render_text_with_urls(rawDescription, user['legacy']['entities']['description']['urls'])
		link = None
		if user['legacy'].get('url'):
			entity = user['legacy']['entities'].get('url', {}).get('urls', [None])[0]
			if not entity or entity['url'] != user['legacy']['url']:
				self.logger.warning(f'Link inconsistency on user')
			if not entity:
				entity = {'indices': (0, len(user['legacy']['url']))}
			link = TextLink(text = entity.get('display_url'), url = entity.get('expanded_url', user['legacy']['url']), tcourl = user['legacy']['url'], indices = tuple(entity['indices']))
		label = None
		if (labelO := user['affiliates_highlighted_label'].get('label')):
			label = self._user_label_to_user_label(labelO)
		return User(
			username = user['legacy']['screen_name'],
			id = int(user['rest_id']),
			displayname = user['legacy']['name'],
			rawDescription = rawDescription,
			renderedDescription = renderedDescription,
			descriptionLinks = [TextLink(
			                      text = x.get('display_url'),
			                      url = x['expanded_url'],
			                      tcourl = x['url'],
			                      indices = tuple(x['indices']),
			                    ) for x in user['legacy']['entities']['description']['urls']],
			verified = user['legacy']['verified'],
			created = email.utils.parsedate_to_datetime(user['legacy']['created_at']),
			followersCount = user['legacy']['followers_count'],
			friendsCount = user['legacy']['friends_count'],
			statusesCount = user['legacy']['statuses_count'],
			favouritesCount = user['legacy']['favourites_count'],
			listedCount = user['legacy']['listed_count'],
			mediaCount = user['legacy']['media_count'],
			location = user['legacy']['location'],
			protected = user['legacy']['protected'],
			link = link,
			profileImageUrl = user['legacy']['profile_image_url_https'],
			profileBannerUrl = user['legacy'].get('profile_banner_url'),
			label = label,
		  )

	def get_items(self):
		if self._isUserId:
			# Resolve user ID to username
			self._user = self.entity.username
			self._isUserId = False
			self._query = f'from:{self._user}'
		yield from super().get_items()

	@staticmethod
	def is_valid_username(s):
		return 1 <= len(s) <= 15 and s.strip(string.ascii_letters + string.digits + '_') == ''

	@classmethod
	def _cli_setup_parser(cls, subparser):
		def user(s):
			if cls.is_valid_username(s) or s.isdigit():
				return s
			raise ValueError('Invalid username or ID')

		subparser.add_argument('--user-id', dest = 'isUserId', action = 'store_true', default = False, help = 'Use user ID instead of username')
		subparser.add_argument('user', type = user, help = 'A Twitter username (without @)')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, user = int(args.user) if args.isUserId else args.user)


class TwitterProfileScraper(TwitterUserScraper):
	name = 'twitter-profile'

	def get_items(self):
		if not self._isUserId:
			userId = self.entity.id
		else:
			userId = self._user
		paginationVariables = {
			'userId': userId,
			'count': 100,
			'cursor': None,
			'includePromotedContent': True,
			'withCommunity': True,
			'withSuperFollowsUserFields': True,
			'withDownvotePerspective': False,
			'withReactionsMetadata': False,
			'withReactionsPerspective': False,
			'withSuperFollowsTweetFields': True,
			'withVoice': True,
			'withV2Timeline': False,
		}
		variables = paginationVariables.copy()
		del variables['cursor']

		gotPinned = False
		for obj in self._iter_api_data('https://twitter.com/i/api/graphql/BSKxQ9_IaCoVyIvQHQROIQ/UserTweetsAndReplies', _TwitterAPIType.GRAPHQL, variables, paginationVariables):
			instructions = obj['data']['user']['result']['timeline']['timeline']['instructions']
			if not gotPinned:
				for instruction in instructions:
					if instruction['type'] == 'TimelinePinEntry':
						gotPinned = True
						yield self._graphql_timeline_tweet_item_result_to_tweet(instruction['entry']['content']['itemContent']['tweet_results']['result'])
			yield from self._graphql_timeline_instructions_to_tweets(instructions)


class TwitterHashtagScraper(TwitterSearchScraper):
	name = 'twitter-hashtag'

	def __init__(self, hashtag, **kwargs):
		super().__init__(f'#{hashtag}', **kwargs)
		self._hashtag = hashtag

	@classmethod
	def _cli_setup_parser(cls, subparser):
		subparser.add_argument('hashtag', type = snscrape.base.nonempty_string('hashtag'), help = 'A Twitter hashtag (without #)')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, args.hashtag)


class TwitterTweetScraperMode(enum.Enum):
	SINGLE = 'single'
	SCROLL = 'scroll'
	RECURSE = 'recurse'

	@classmethod
	def _cli_from_args(cls, args):
		if args.scroll:
			return cls.SCROLL
		if args.recurse:
			return cls.RECURSE
		return cls.SINGLE


class TwitterTweetScraper(_TwitterAPIScraper):
	name = 'twitter-tweet'

	def __init__(self, tweetId, *, mode = TwitterTweetScraperMode.SINGLE, **kwargs):
		self._tweetId = tweetId
		self._mode = mode
		super().__init__(f'https://twitter.com/i/web/status/{self._tweetId}', **kwargs)

	def get_items(self):
		paginationVariables = {
			'focalTweetId': str(self._tweetId),
			'cursor': None,
			'referrer': 'tweet',
			'with_rux_injections': False,
			'includePromotedContent': True,
			'withCommunity': True,
			'withQuickPromoteEligibilityTweetFields': True,
			'withTweetQuoteCount': True,
			'withBirdwatchNotes': True,
			'withSuperFollowsUserFields': True,
			'withBirdwatchPivots': False,
			'withDownvotePerspective': False,
			'withReactionsMetadata': False,
			'withReactionsPerspective': False,
			'withSuperFollowsTweetFields': True,
			'withVoice': True,
			'withV2Timeline': False,
		}
		variables = paginationVariables.copy()
		del variables['cursor'], variables['referrer']
		url = 'https://twitter.com/i/api/graphql/8svRea_Lc0_mdhwP6dqe0Q/TweetDetail'
		if self._mode is TwitterTweetScraperMode.SINGLE:
			obj = self._get_api_data(url, _TwitterAPIType.GRAPHQL, params = variables)
			if not obj['data']:
				return
			for instruction in obj['data']['threaded_conversation_with_injections']['instructions']:
				if instruction['type'] != 'TimelineAddEntries':
					continue
				for entry in instruction['entries']:
					if entry['entryId'] == f'tweet-{self._tweetId}' and entry['content']['entryType'] == 'TimelineTimelineItem' and entry['content']['itemContent']['itemType'] == 'TimelineTweet':
						yield self._graphql_timeline_tweet_item_result_to_tweet(entry['content']['itemContent']['tweet_results']['result'])
						break
		elif self._mode is TwitterTweetScraperMode.SCROLL:
			for obj in self._iter_api_data(url, _TwitterAPIType.GRAPHQL, variables, paginationVariables, direction = _ScrollDirection.BOTH):
				if not obj['data']:
					continue
				yield from self._graphql_timeline_instructions_to_tweets(obj['data']['threaded_conversation_with_injections']['instructions'], includeConversationThreads = True)
		elif self._mode is TwitterTweetScraperMode.RECURSE:
			seenTweets = set()
			queue = collections.deque()
			queue.append(self._tweetId)
			while queue:
				tweetId = queue.popleft()
				thisPagVariables = paginationVariables.copy()
				thisPagVariables['focalTweetId'] = str(tweetId)
				thisVariables = thisPagVariables.copy()
				del thisPagVariables['cursor'], thisPagVariables['referrer']
				for obj in self._iter_api_data(url, _TwitterAPIType.GRAPHQL, thisVariables, thisPagVariables, direction = _ScrollDirection.BOTH):
					if not obj['data']:
						continue
					for tweet in self._graphql_timeline_instructions_to_tweets(obj['data']['threaded_conversation_with_injections']['instructions'], includeConversationThreads = True):
						if tweet.id not in seenTweets:
							yield tweet
							seenTweets.add(tweet.id)
							if tweet.id != self._tweetId:  # Already queued at the beginning
								queue.append(tweet.id)

	@classmethod
	def _cli_setup_parser(cls, subparser):
		group = subparser.add_mutually_exclusive_group(required = False)
		group.add_argument('--scroll', action = 'store_true', default = False, help = 'Enable scrolling in both directions')
		group.add_argument('--recurse', '--recursive', action = 'store_true', default = False, help = 'Enable recursion through all tweets encountered (warning: slow, potentially memory-intensive!)')
		subparser.add_argument('tweetId', type = int, help = 'A tweet ID')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, args.tweetId, mode = TwitterTweetScraperMode._cli_from_args(args))


class TwitterListPostsScraper(TwitterSearchScraper):
	name = 'twitter-list-posts'

	def __init__(self, listName, **kwargs):
		super().__init__(f'list:{listName}', **kwargs)
		self._listName = listName

	@classmethod
	def _cli_setup_parser(cls, subparser):
		subparser.add_argument('list', type = snscrape.base.nonempty_string('list'), help = 'A Twitter list ID or a string of the form "username/listname" (replace spaces with dashes)')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, args.list)


class TwitterTrendsScraper(_TwitterAPIScraper):
	name = 'twitter-trends'

	def __init__(self, **kwargs):
		super().__init__('https://twitter.com/i/trends', **kwargs)

	def get_items(self):
		params = {
			'include_profile_interstitial_type': '1',
			'include_blocking': '1',
			'include_blocked_by': '1',
			'include_followed_by': '1',
			'include_want_retweets': '1',
			'include_mute_edge': '1',
			'include_can_dm': '1',
			'include_can_media_tag': '1',
			'include_ext_has_nft_avatar': '1',
			'skip_status': '1',
			'cards_platform': 'Web-12',
			'include_cards': '1',
			'include_ext_alt_text': 'true',
			'include_quote_count': 'true',
			'include_reply_count': '1',
			'tweet_mode': 'extended',
			'include_entities': 'true',
			'include_user_entities': 'true',
			'include_ext_media_color': 'true',
			'include_ext_media_availability': 'true',
			'include_ext_sensitive_media_warning': 'true',
			'include_ext_trusted_friends_metadata': 'true',
			'send_error_codes': 'true',
			'simple_quoted_tweet': 'true',
			'count': '20',
			'candidate_source': 'trends',
			'include_page_configuration': 'false',
			'entity_tokens': 'false',
			'ext': 'mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,enrichments,superFollowMetadata,unmentionInfo',
		}
		obj = self._get_api_data('https://twitter.com/i/api/2/guide.json', _TwitterAPIType.V2, params)
		for instruction in obj['timeline']['instructions']:
			if not 'addEntries' in instruction:
				continue
			for entry in instruction['addEntries']['entries']:
				if entry['entryId'] != 'trends':
					continue
				for item in entry['content']['timelineModule']['items']:
					trend = item['item']['content']['trend']
					yield Trend(name = trend['name'], metaDescription = trend['trendMetadata'].get('metaDescription'), domainContext = trend['trendMetadata']['domainContext'])
