import collections
import dataclasses
import datetime
import email.utils
import enum
import itertools
import json
import random
import logging
import re
import snscrape.base
import string
import time
import typing
import urllib.parse


logger = logging.getLogger(__name__)
_API_AUTHORIZATION_HEADER = 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA'


@dataclasses.dataclass
class Tweet(snscrape.base.Item):
	url: str
	date: datetime.datetime
	content: str
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
	outlinks: typing.Optional[typing.List[str]] = None
	tcooutlinks: typing.Optional[typing.List[str]] = None
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

	username = snscrape.base._DeprecatedProperty('username', lambda self: self.user.username, 'user.username')
	outlinksss = snscrape.base._DeprecatedProperty('outlinksss', lambda self: ' '.join(self.outlinks) if self.outlinks else '', 'outlinks')
	tcooutlinksss = snscrape.base._DeprecatedProperty('tcooutlinksss', lambda self: ' '.join(self.tcooutlinks) if self.tcooutlinks else '', 'tcooutlinks')

	def __str__(self):
		return self.url


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
	duration: float
	views: typing.Optional[int] = None


@dataclasses.dataclass
class Gif(Medium):
	thumbnailUrl: str
	variants: typing.List[VideoVariant]


@dataclasses.dataclass
class DescriptionURL:
	text: typing.Optional[str]
	url: str
	tcourl: str
	indices: typing.Tuple[int, int]


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


@dataclasses.dataclass
class User(snscrape.base.Entity):
	# Most fields can be None if they're not known.

	username: str
	id: int
	displayname: typing.Optional[str] = None
	description: typing.Optional[str] = None # Description as it's displayed on the web interface with URLs replaced
	rawDescription: typing.Optional[str] = None # Raw description with the URL(s) intact
	descriptionUrls: typing.Optional[typing.List[DescriptionURL]] = None
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
	linkUrl: typing.Optional[str] = None
	linkTcourl: typing.Optional[str] = None
	profileImageUrl: typing.Optional[str] = None
	profileBannerUrl: typing.Optional[str] = None
	label: typing.Optional['UserLabel'] = None

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
class Trend(snscrape.base.Item):
	name: str
	domainContext: str
	metaDescription: typing.Optional[str] = None

	def __str__(self):
		return f'https://twitter.com/search?q={urllib.parse.quote(self.name)}'


class ScrollDirection(enum.Enum):
	TOP = enum.auto()
	BOTTOM = enum.auto()
	BOTH = enum.auto()


class TwitterAPIScraper(snscrape.base.Scraper):
	def __init__(self, baseUrl, **kwargs):
		super().__init__(**kwargs)
		self._baseUrl = baseUrl
		self._guestToken = None
		self._userAgent = f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.{random.randint(0, 9999)} Safari/537.{random.randint(0, 99)}'
		self._apiHeaders = {
			'User-Agent': self._userAgent,
			'Authorization': _API_AUTHORIZATION_HEADER,
			'Referer': self._baseUrl,
			'Accept-Language': 'en-US,en;q=0.5',
		}

	def _ensure_guest_token(self, url = None):
		if self._guestToken is not None:
			return
		logger.info('Retrieving guest token')
		r = self._get(self._baseUrl if url is None else url, headers = {'User-Agent': self._userAgent})
		if (match := re.search(r'document\.cookie = decodeURIComponent\("gt=(\d+); Max-Age=10800; Domain=\.twitter\.com; Path=/; Secure"\);', r.text)):
			logger.debug('Found guest token in HTML')
			self._guestToken = match.group(1)
		if 'gt' in r.cookies:
			logger.debug('Found guest token in cookies')
			self._guestToken = r.cookies['gt']
		if self._guestToken:
			self._session.cookies.set('gt', self._guestToken, domain = '.twitter.com', path = '/', secure = True, expires = time.time() + 10800)
			self._apiHeaders['x-guest-token'] = self._guestToken
			return
		raise snscrape.base.ScraperException('Unable to find guest token')

	def _unset_guest_token(self):
		self._guestToken = None
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

	def _get_api_data(self, endpoint, params):
		self._ensure_guest_token()
		r = self._get(endpoint, params = params, headers = self._apiHeaders, responseOkCallback = self._check_api_response)
		try:
			obj = r.json()
		except json.JSONDecodeError as e:
			raise snscrape.base.ScraperException('Received invalid JSON from Twitter') from e
		return obj

	def _iter_api_data(self, endpoint, params, paginationParams = None, cursor = None, direction = ScrollDirection.BOTTOM):
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
		if direction is ScrollDirection.TOP or direction is ScrollDirection.BOTH:
			dir = 'top'
		else:
			dir = 'bottom'
		stopOnEmptyResponse = False
		emptyResponsesOnCursor = 0
		while True:
			logger.info(f'Retrieving scroll page {cursor}')
			obj = self._get_api_data(endpoint, reqParams)
			yield obj

			# No data format test, just a hard and loud crash if anything's wrong :-)
			newCursor = None
			promptCursor = None
			newBottomCursorAndStop = None
			for instruction in obj['timeline']['instructions']:
				if 'addEntries' in instruction:
					entries = instruction['addEntries']['entries']
				elif 'replaceEntry' in instruction:
					entries = [instruction['replaceEntry']['entry']]
				else:
					continue
				for entry in entries:
					if entry['entryId'] == f'sq-cursor-{dir}' or entry['entryId'].startswith(f'cursor-{dir}-'):
						newCursor = entry['content']['operation']['cursor']['value']
						if 'stopOnEmptyResponse' in entry['content']['operation']['cursor']:
							stopOnEmptyResponse = entry['content']['operation']['cursor']['stopOnEmptyResponse']
					elif entry['entryId'].startswith('cursor-showMoreThreadsPrompt-'): # E.g. 'offensive' replies button
						promptCursor = entry['content']['operation']['cursor']['value']
					elif direction is ScrollDirection.BOTH and bottomCursorAndStop is None and (entry['entryId'] == f'sq-cursor-bottom' or entry['entryId'].startswith('cursor-bottom-')):
						newBottomCursorAndStop = (entry['content']['operation']['cursor']['value'], entry['content']['operation']['cursor'].get('stopOnEmptyResponse', False))
			if bottomCursorAndStop is None and newBottomCursorAndStop is not None:
				bottomCursorAndStop = newBottomCursorAndStop
			if newCursor == cursor and self._count_tweets(obj) == 0:
				# Twitter sometimes returns the same cursor as requested and no results even though there are more results.
				# When this happens, retry the same cursor up to the retries setting.
				emptyResponsesOnCursor += 1
				if emptyResponsesOnCursor > self._retries:
					break
			if not newCursor or (stopOnEmptyResponse and self._count_tweets(obj) == 0):
				# End of pagination
				if promptCursor is not None:
					newCursor = promptCursor
				elif direction is ScrollDirection.BOTH and bottomCursorAndStop is not None:
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

	def _count_tweets(self, obj):
		count = 0
		for instruction in obj['timeline']['instructions']:
			if 'addEntries' in instruction:
				entries = instruction['addEntries']['entries']
			elif 'replaceEntry' in instruction:
				entries = [instruction['replaceEntry']['entry']]
			else:
				continue
			for entry in entries:
				if entry['entryId'].startswith('sq-I-t-') or entry['entryId'].startswith('tweet-'):
					count += 1
		return count

	def _instructions_to_tweets(self, obj, includeConversationThreads = False):
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
					yield from self._instruction_tweet_entry_to_tweet(entry['entryId'], entry['content'], obj)
				elif includeConversationThreads and entry['entryId'].startswith('conversationThread-') and not entry['entryId'].endswith('-show_more_cursor'):
					for item in entry['content']['timelineModule']['items']:
						if item['entryId'].startswith('tweet-'):
							yield from self._instruction_tweet_entry_to_tweet(item['entryId'], item, obj)

	def _instruction_tweet_entry_to_tweet(self, entryId, entry, obj):
		if 'tweet' in entry['item']['content']:
			if 'promotedMetadata' in entry['item']['content']['tweet']: # Promoted tweet aka ads
				return
			if entry['item']['content']['tweet']['id'] not in obj['globalObjects']['tweets']:
				logger.warning(f'Skipping tweet {entry["item"]["content"]["tweet"]["id"]} which is not in globalObjects')
				return
			tweet = obj['globalObjects']['tweets'][entry['item']['content']['tweet']['id']]
		elif 'tombstone' in entry['item']['content']:
			if 'tweet' not in entry['item']['content']['tombstone']: # E.g. deleted reply
				return
			if entry['item']['content']['tombstone']['tweet']['id'] not in obj['globalObjects']['tweets']:
				logger.warning(f'Skipping tweet {entry["item"]["content"]["tombstone"]["tweet"]["id"]} which is not in globalObjects')
				return
			tweet = obj['globalObjects']['tweets'][entry['item']['content']['tombstone']['tweet']['id']]
		else:
			raise snscrape.base.ScraperException(f'Unable to handle entry {entryId!r}')
		yield self._tweet_to_tweet(tweet, obj)

	def _tweet_to_tweet(self, tweet, obj):
		# Transforms a Twitter API tweet object into a Tweet
		kwargs = {}
		kwargs['id'] = tweet['id'] if 'id' in tweet else int(tweet['id_str'])
		kwargs['content'] = tweet['full_text']
		kwargs['renderedContent'] = self._render_text_with_urls(tweet['full_text'], tweet['entities'].get('urls'))
		kwargs['user'] = self._user_to_user(obj['globalObjects']['users'][tweet['user_id_str']])
		kwargs['date'] = email.utils.parsedate_to_datetime(tweet['created_at'])
		if tweet['entities'].get('urls'):
			kwargs['outlinks'] = [u['expanded_url'] for u in tweet['entities']['urls']]
			kwargs['tcooutlinks'] = [u['url'] for u in tweet['entities']['urls']]
		kwargs['url'] = f'https://twitter.com/{obj["globalObjects"]["users"][tweet["user_id_str"]]["screen_name"]}/status/{kwargs["id"]}'
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
				if medium['type'] == 'photo':
					if '.' not in medium['media_url_https']:
						logger.warning(f'Skipping malformed medium URL on tweet {kwargs["id"]}: {medium["media_url_https"]!r} contains no dot')
						continue
					baseUrl, format = medium['media_url_https'].rsplit('.', 1)
					if format not in ('jpg', 'png'):
						logger.warning(f'Skipping photo with unknown format on tweet {kwargs["id"]}: {format!r}')
						continue
					media.append(Photo(
						previewUrl = f'{baseUrl}?format={format}&name=small',
						fullUrl = f'{baseUrl}?format={format}&name=large',
					))
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
						if (ext := medium['ext']) and (mediaStats := ext['mediaStats']) and isinstance(r := mediaStats['r'], dict) and 'ok' in r and isinstance(r['ok'], dict):
							mKwargs['views'] = int(r['ok']['viewCount'])
						cls = Video
					elif medium['type'] == 'animated_gif':
						cls = Gif
					media.append(cls(**mKwargs))
			if media:
				kwargs['media'] = media
		if 'retweeted_status_id_str' in tweet:
			kwargs['retweetedTweet'] = self._tweet_to_tweet(obj['globalObjects']['tweets'][tweet['retweeted_status_id_str']], obj)
		if 'quoted_status_id_str' in tweet and tweet['quoted_status_id_str'] in obj['globalObjects']['tweets']:
			kwargs['quotedTweet'] = self._tweet_to_tweet(obj['globalObjects']['tweets'][tweet['quoted_status_id_str']], obj)
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
			if 'coordinates' not in kwargs and tweet['place']['bounding_box'] and (coords := tweet['place']['bounding_box']['coordinates']) and coords[0] and len(coords[0][0]) == 2:
				# Take the first (longitude, latitude) couple of the "place square"
				kwargs['coordinates'] = Coordinates(coords[0][0][0], coords[0][0][1])
		if tweet['entities'].get('hashtags'):
			kwargs['hashtags'] = [o['text'] for o in tweet['entities']['hashtags']]
		if tweet['entities'].get('symbols'):
			kwargs['cashtags'] = [o['text'] for o in tweet['entities']['symbols']]
		return Tweet(**kwargs)

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

	def _user_to_user(self, user):
		kwargs = {}
		kwargs['username'] = user['screen_name']
		kwargs['id'] = user['id'] if 'id' in user else int(user['id_str'])
		kwargs['displayname'] = user['name']
		kwargs['description'] = self._render_text_with_urls(user['description'], user['entities']['description'].get('urls'))
		kwargs['rawDescription'] = user['description']
		if user['entities']['description'].get('urls'):
			kwargs['descriptionUrls'] = [{'text': x.get('display_url'), 'url': x['expanded_url'], 'tcourl': x['url'], 'indices': tuple(x['indices'])} for x in user['entities']['description']['urls']]
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
		if 'url' in user['entities']:
			kwargs['linkUrl'] = (user['entities']['url']['urls'][0].get('expanded_url') or user.get('url'))
		kwargs['linkTcourl'] = user.get('url')
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


class TwitterSearchScraper(TwitterAPIScraper):
	name = 'twitter-search'

	def __init__(self, query, cursor = None, top = False, **kwargs):
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
			return False, f'content type is not JSON'
		if r.status_code != 200:
			return False, f'non-200 status code'
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
			'send_error_codes': 'true',
			'simple_quoted_tweets': 'true',
			'q': self._query,
			'tweet_search_mode': 'live',
			'count': '100',
			'query_source': 'spelling_expansion_revert_click',
			'cursor': None,
			'pc': '1',
			'spelling_corrections': '1',
			'ext': 'mediaStats,highlightedLabel',
		}
		params = paginationParams.copy()
		del params['cursor']

		if self._top:
			del params['tweet_search_mode']
			del paginationParams['tweet_search_mode']

		for obj in self._iter_api_data('https://api.twitter.com/2/search/adaptive.json', params, paginationParams, cursor = self._cursor):
			yield from self._instructions_to_tweets(obj)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('--cursor', metavar = 'CURSOR')
		subparser.add_argument('--top', action = 'store_true', default = False, help = 'Enable fetching top tweets instead of live/chronological')
		subparser.add_argument('query', type = snscrape.base.nonempty_string('query'), help = 'A Twitter search string')

	@classmethod
	def from_args(cls, args):
		return cls._construct(args, args.query, cursor = args.cursor, top = args.top)


class TwitterUserScraper(TwitterSearchScraper):
	name = 'twitter-user'

	def __init__(self, username, isUserId, **kwargs):
		if not self.is_valid_username(username):
			raise ValueError('Invalid username')
		super().__init__(f'from:{username}', **kwargs)
		self._username = username
		self._isUserId = isUserId
		self._baseUrl = f'https://twitter.com/{self._username}' if not self._isUserId else f'https://twitter.com/i/user/{self._username}'

	def _get_entity(self):
		self._ensure_guest_token()
		if not self._isUserId:
			fieldName = 'screen_name'
			endpoint = 'https://api.twitter.com/graphql/-xfUfZsnR_zqjFd-IfrN5A/UserByScreenName'
		else:
			fieldName = 'userId'
			endpoint = 'https://twitter.com/i/api/graphql/WN6Hck-Pwm-YP0uxVj1oMQ/UserByRestIdWithoutResults'
		params = {'variables': json.dumps({fieldName: self._username, 'withHighlightedLabel': True}, separators = (',', ':'))}
		obj = self._get_api_data(endpoint, params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote))
		if not obj['data']:
			return None
		user = obj['data']['user']
		rawDescription = user['legacy']['description']
		description = self._render_text_with_urls(rawDescription, user['legacy']['entities']['description']['urls'])
		label = None
		if (labelO := user['affiliates_highlighted_label'].get('label')):
			label = self._user_label_to_user_label(labelO)
		return User(
			username = user['legacy']['screen_name'],
			id = user['rest_id'],
			displayname = user['legacy']['name'],
			description = description,
			rawDescription = rawDescription,
			descriptionUrls = [{'text': x.get('display_url'), 'url': x['expanded_url'], 'tcourl': x['url'], 'indices': tuple(x['indices'])} for x in user['legacy']['entities']['description']['urls']],
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
			linkUrl = user['legacy']['entities']['url']['urls'][0]['expanded_url'] if 'url' in user['legacy']['entities'] else None,
			linkTcourl = user['legacy'].get('url'),
			profileImageUrl = user['legacy']['profile_image_url_https'],
			profileBannerUrl = user['legacy'].get('profile_banner_url'),
			label = label,
		  )

	def get_items(self):
		if self._isUserId:
			# Resolve user ID to username
			self._username = self.entity.username
			self._isUserId = False
			self._query = f'from:{self._username}'
		yield from super().get_items()

	@staticmethod
	def is_valid_username(s):
		return (1 <= len(s) <= 15 and s.strip(string.ascii_letters + string.digits + '_') == '') or (s and s.strip(string.digits) == '')

	@classmethod
	def setup_parser(cls, subparser):
		def username(s):
			if cls.is_valid_username(s):
				return s
			raise ValueError('Invalid username')

		subparser.add_argument('--user-id', dest = 'isUserId', action = 'store_true', default = False, help = 'Use user ID instead of username')
		subparser.add_argument('username', type = username, help = 'A Twitter username (without @)')

	@classmethod
	def from_args(cls, args):
		return cls._construct(args, args.username, args.isUserId)


class TwitterProfileScraper(TwitterUserScraper):
	name = 'twitter-profile'

	def get_items(self):
		if not self._isUserId:
			userId = self.entity.id
		else:
			userId = self._username
		paginationParams = {
			'include_profile_interstitial_type': '1',
			'include_blocking': '1',
			'include_blocked_by': '1',
			'include_followed_by': '1',
			'include_want_retweets': '1',
			'include_mute_edge': '1',
			'include_can_dm': '1',
			'include_can_media_tag': '1',
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
			'send_error_codes': 'true',
			'simple_quoted_tweets': 'true',
			'include_tweet_replies': 'true',
			'userId': userId,
			'count': '100',
			'cursor': None,
			'ext': 'mediaStats,highlightedLabel',
		}
		params = paginationParams.copy()
		del params['cursor']

		for obj in self._iter_api_data(f'https://api.twitter.com/2/timeline/profile/{userId}.json', params, paginationParams):
			yield from self._instructions_to_tweets(obj)


class TwitterHashtagScraper(TwitterSearchScraper):
	name = 'twitter-hashtag'

	def __init__(self, hashtag, **kwargs):
		super().__init__(f'#{hashtag}', **kwargs)
		self._hashtag = hashtag

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('hashtag', type = snscrape.base.nonempty_string('hashtag'), help = 'A Twitter hashtag (without #)')

	@classmethod
	def from_args(cls, args):
		return cls._construct(args, args.hashtag)


class TwitterTweetScraperMode(enum.Enum):
	SINGLE = 'single'
	SCROLL = 'scroll'
	RECURSE = 'recurse'

	@classmethod
	def from_args(cls, args):
		if args.scroll:
			return cls.SCROLL
		if args.recurse:
			return cls.RECURSE
		return cls.SINGLE


class TwitterTweetScraper(TwitterAPIScraper):
	name = 'twitter-tweet'

	def __init__(self, tweetId, mode, **kwargs):
		self._tweetId = tweetId
		self._mode = mode
		super().__init__(f'https://twitter.com/i/web/{self._tweetId}', **kwargs)

	def get_items(self):
		paginationParams = {
			'include_profile_interstitial_type': '1',
			'include_blocking': '1',
			'include_blocked_by': '1',
			'include_followed_by': '1',
			'include_want_retweets': '1',
			'include_mute_edge': '1',
			'include_can_dm': '1',
			'include_can_media_tag': '1',
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
			'send_error_codes': 'true',
			'simple_quoted_tweet': 'true',
			'count': '20',
			'cursor': None,
			'include_ext_has_birdwatch_notes': 'false',
			'ext': 'mediaStats,highlightedLabel',
		}
		params = paginationParams.copy()
		del params['cursor']
		if self._mode is TwitterTweetScraperMode.SINGLE:
			obj = self._get_api_data(f'https://twitter.com/i/api/2/timeline/conversation/{self._tweetId}.json', params)
			yield self._tweet_to_tweet(obj['globalObjects']['tweets'][str(self._tweetId)], obj)
		elif self._mode is TwitterTweetScraperMode.SCROLL:
			for obj in self._iter_api_data(f'https://twitter.com/i/api/2/timeline/conversation/{self._tweetId}.json', params, paginationParams, direction = ScrollDirection.BOTH):
				yield from self._instructions_to_tweets(obj, includeConversationThreads = True)
		elif self._mode is TwitterTweetScraperMode.RECURSE:
			seenTweets = set()
			queue = collections.deque()
			queue.append(self._tweetId)
			while queue:
				tweetId = queue.popleft()
				for obj in self._iter_api_data(f'https://twitter.com/i/api/2/timeline/conversation/{tweetId}.json', params, paginationParams, direction = ScrollDirection.BOTH):
					for tweet in self._instructions_to_tweets(obj, includeConversationThreads = True):
						if tweet.id not in seenTweets:
							yield tweet
							seenTweets.add(tweet.id)
							if tweet.replyCount:
								queue.append(tweet.id)

	@classmethod
	def setup_parser(cls, subparser):
		group = subparser.add_mutually_exclusive_group(required = False)
		group.add_argument('--scroll', action = 'store_true', default = False, help = 'Enable scrolling in both directions')
		group.add_argument('--recurse', '--recursive', action = 'store_true', default = False, help = 'Enable recursion through all tweets encountered (warning: slow, potentially memory-intensive!)')
		subparser.add_argument('tweetId', type = int, help = 'A tweet ID')

	@classmethod
	def from_args(cls, args):
		return cls._construct(args, args.tweetId, TwitterTweetScraperMode.from_args(args))


class TwitterListPostsScraper(TwitterSearchScraper):
	name = 'twitter-list-posts'

	def __init__(self, listName, **kwargs):
		super().__init__(f'list:{listName}', **kwargs)
		self._listName = listName

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('list', type = snscrape.base.nonempty_string('list'), help = 'A Twitter list ID or a string of the form "username/listname" (replace spaces with dashes)')

	@classmethod
	def from_args(cls, args):
		return cls._construct(args, args.list)


class TwitterTrendsScraper(TwitterAPIScraper):
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
			'send_error_codes': 'true',
			'simple_quoted_tweet': 'true',
			'count': '20',
			'candidate_source': 'trends',
			'include_page_configuration': 'false',
			'entity_tokens': 'false',
			'ext': 'mediaStats,highlightedLabel,voiceInfo',
		}
		obj = self._get_api_data('https://twitter.com/i/api/2/guide.json', params)
		for instruction in obj['timeline']['instructions']:
			if not 'addEntries' in instruction:
				continue
			for entry in instruction['addEntries']['entries']:
				if entry['entryId'] != 'trends':
					continue
				for item in entry['content']['timelineModule']['items']:
					trend = item['item']['content']['trend']
					yield Trend(name = trend['name'], metaDescription = trend['trendMetadata'].get('metaDescription'), domainContext = trend['trendMetadata']['domainContext'])
