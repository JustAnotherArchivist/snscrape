import bs4
import dataclasses
import datetime
import email.utils
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
	outlinks: list
	tcooutlinks: list
	replyCount: int
	retweetCount: int
	likeCount: int
	quoteCount: int
	conversationId: int
	lang: str
	source: str
	sourceUrl: typing.Optional[str] = None
	sourceLabel: typing.Optional[str] = None
	media: typing.Optional[typing.List['Medium']] = None
	retweetedTweet: typing.Optional['Tweet'] = None
	quotedTweet: typing.Optional['Tweet'] = None
	mentionedUsers: typing.Optional[typing.List['User']] = None

	username = snscrape.base._DeprecatedProperty('username', lambda self: self.user.username, 'user.username')
	outlinksss = snscrape.base._DeprecatedProperty('outlinksss', lambda self: ' '.join(self.outlinks), 'outlinks')
	tcooutlinksss = snscrape.base._DeprecatedProperty('tcooutlinksss', lambda self: ' '.join(self.tcooutlinks), 'tcooutlinks')

	def __str__(self):
		return self.url


class Medium:
	pass


@dataclasses.dataclass
class Photo(Medium):
	previewUrl: str
	fullUrl: str
	type: str = 'photo'


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
	type: str = 'video'


@dataclasses.dataclass
class Gif(Medium):
	thumbnailUrl: str
	variants: typing.List[VideoVariant]
	type: str = 'gif'


@dataclasses.dataclass
class DescriptionURL:
	text: str
	url: str
	tcourl: str
	indices: typing.Tuple[int, int]


@dataclasses.dataclass
class User(snscrape.base.Entity):
	# Most fields can be None if they're not known.

	username: str
	displayname: str
	id: str # Seems to always be numeric, but the API returns it as a string, so it might also contain other things in the future
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

	@property
	def url(self):
		return f'https://twitter.com/{self.username}'

	def __str__(self):
		return self.url


class TwitterOldDesignScraper(snscrape.base.Scraper):
	def _feed_to_items(self, feed):
		for tweet in feed:
			username = tweet.find('span', 'username').find('b').text
			tweetID = tweet['data-item-id']
			url = f'https://twitter.com/{username}/status/{tweetID}'

			date = None
			if (timestampA := tweet.find('a', 'tweet-timestamp')):
				timestampSpan = timestampA.find('span', '_timestamp')
				if timestampSpan and timestampSpan.has_attr('data-time'):
					date = datetime.datetime.fromtimestamp(int(timestampSpan['data-time']), datetime.timezone.utc)
			if not date:
				logger.warning(f'Failed to extract date for {url}')

			content = None
			outlinks = []
			tcooutlinks = []
			if (contentP := tweet.find('p', 'tweet-text')):
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
			if (card := tweet.find('div', 'card2')) and 'has-autoplayable-media' not in card['class']:
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
		if r.status_code == 429:
			self._unset_guest_token()
			self._ensure_guest_token()
			return False, 'rate-limited'
		if r.headers.get('content-type').replace(' ', '') != 'application/json;charset=utf-8':
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

	def _iter_api_data(self, endpoint, params, paginationParams = None, cursor = None):
		# Iterate over endpoint with params/paginationParams, optionally starting from a cursor
		# Handles guest token extraction using the baseUrl passed to __init__ etc.
		# Order from params and paginationParams is preserved. To insert the cursor at a particular location, insert a 'cursor' key into paginationParams there (value is overwritten).
		if cursor is None:
			reqParams = params
		else:
			reqParams = paginationParams.copy()
			reqParams['cursor'] = cursor
		stopOnEmptyResponse = False
		while True:
			logger.info(f'Retrieving scroll page {cursor}')
			obj = self._get_api_data(endpoint, reqParams)
			yield obj

			# No data format test, just a hard and loud crash if anything's wrong :-)
			newCursor = None
			for instruction in obj['timeline']['instructions']:
				if 'addEntries' in instruction:
					entries = instruction['addEntries']['entries']
				elif 'replaceEntry' in instruction:
					entries = [instruction['replaceEntry']['entry']]
				else:
					continue
				for entry in entries:
					if entry['entryId'] == 'sq-cursor-bottom' or entry['entryId'].startswith('cursor-bottom-'):
						newCursor = entry['content']['operation']['cursor']['value']
						if 'stopOnEmptyResponse' in entry['content']['operation']['cursor']:
							stopOnEmptyResponse = entry['content']['operation']['cursor']['stopOnEmptyResponse']
			if not newCursor or newCursor == cursor or (stopOnEmptyResponse and self._count_tweets(obj) == 0):
				# End of pagination
				break
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

	def _instructions_to_tweets(self, obj):
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
					if 'tweet' in entry['content']['item']['content']:
						if 'promotedMetadata' in entry['content']['item']['content']['tweet']: # Promoted tweet aka ads
							continue
						if entry['content']['item']['content']['tweet']['id'] not in obj['globalObjects']['tweets']:
							logger.warning(f'Skipping tweet {entry["content"]["item"]["content"]["tweet"]["id"]} which is not in globalObjects')
							continue
						tweet = obj['globalObjects']['tweets'][entry['content']['item']['content']['tweet']['id']]
					elif 'tombstone' in entry['content']['item']['content'] and 'tweet' in entry['content']['item']['content']['tombstone']:
						if entry['content']['item']['content']['tombstone']['tweet']['id'] not in obj['globalObjects']['tweets']:
							logger.warning(f'Skipping tweet {entry["content"]["item"]["content"]["tombstone"]["tweet"]["id"]} which is not in globalObjects')
							continue
						tweet = obj['globalObjects']['tweets'][entry['content']['item']['content']['tombstone']['tweet']['id']]
					else:
						raise snscrape.base.ScraperException(f'Unable to handle entry {entry["entryId"]!r}')
					yield self._tweet_to_tweet(tweet, obj)

	def _tweet_to_tweet(self, tweet, obj):
		# Transforms a Twitter API tweet object into a Tweet
		kwargs = {}
		kwargs['id'] = tweet['id'] if 'id' in tweet else int(tweet['id_str'])
		kwargs['content'] = tweet['full_text']
		kwargs['renderedContent'] = self._render_text_with_urls(tweet['full_text'], tweet['entities'].get('urls'))
		kwargs['user'] = self._user_to_user(obj['globalObjects']['users'][tweet['user_id_str']])
		kwargs['date'] = email.utils.parsedate_to_datetime(tweet['created_at'])
		kwargs['outlinks'] = [u['expanded_url'] for u in tweet['entities']['urls']] if 'urls' in tweet['entities'] else []
		kwargs['tcooutlinks'] = [u['url'] for u in tweet['entities']['urls']] if 'urls' in tweet['entities'] else []
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
						variants.append(VideoVariant(contentType = variant['content_type'], url = variant['url'], bitrate = variant.get('bitrate') or None))
					mKwargs = {
						'thumbnailUrl': medium['media_url_https'],
						'variants': variants,
					}
					if medium['type'] == 'video':
						mKwargs['duration'] = medium['video_info']['duration_millis'] / 1000
						cls = Video
					elif medium['type'] == 'animated_gif':
						cls = Gif
					media.append(cls(**mKwargs))
			if media:
				kwargs['media'] = media
		kwargs['retweetedTweet'] = self._tweet_to_tweet(obj['globalObjects']['tweets'][tweet['retweeted_status_id_str']], obj) if 'retweeted_status_id_str' in tweet else None
		if 'quoted_status_id_str' in tweet and tweet['quoted_status_id_str'] in obj['globalObjects']['tweets']:
			kwargs['quotedTweet'] = self._tweet_to_tweet(obj['globalObjects']['tweets'][tweet['quoted_status_id_str']], obj)
		kwargs['mentionedUsers'] = [
			User(username = u['screen_name'], displayname = u['name'], id = u['id'] if 'id' in u else int(u['id_str'])) \
			for u in tweet['entities']['user_mentions']
		  ] if 'user_mentions' in tweet['entities'] and tweet['entities']['user_mentions'] else None
		return Tweet(**kwargs)

	def _render_text_with_urls(self, text, urls):
		if not urls:
			return text
		out = []
		out.append(text[:urls[0]['indices'][0]])
		urlsSorted = sorted(urls, key = lambda x: x['indices'][0]) # Ensure that they're in left to right appearance order
		assert all(url['indices'][1] <= nextUrl['indices'][0] for url, nextUrl in zip(urls, urls[1:])), 'broken URL indices'
		for url, nextUrl in itertools.zip_longest(urls, urls[1:]):
			out.append(url['display_url'])
			out.append(text[url['indices'][1] : nextUrl['indices'][0] if nextUrl is not None else None])
		return ''.join(out)

	def _user_to_user(self, user):
		kwargs = {}
		kwargs['username'] = user['screen_name']
		kwargs['displayname'] = user['name']
		kwargs['id'] = user['id'] if 'id' in user else int(user['id_str'])
		kwargs['description'] = self._render_text_with_urls(user['description'], user['entities']['description'].get('urls'))
		kwargs['rawDescription'] = user['description']
		kwargs['descriptionUrls'] = [{'text': x['display_url'], 'url': x['expanded_url'], 'tcourl': x['url'], 'indices': tuple(x['indices'])} for x in user['entities']['description'].get('urls', [])]
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
		kwargs['linkUrl'] = (user['entities']['url']['urls'][0].get('expanded_url') or user.get('url')) if 'url' in user['entities'] else None
		kwargs['linkTcourl'] = user.get('url')
		kwargs['profileImageUrl'] = user['profile_image_url_https']
		kwargs['profileBannerUrl'] = user.get('profile_banner_url')
		return User(**kwargs)


class TwitterSearchScraper(TwitterAPIScraper):
	name = 'twitter-search'

	def __init__(self, query, cursor = None, **kwargs):
		super().__init__(baseUrl = 'https://twitter.com/search?' + urllib.parse.urlencode({'f': 'live', 'lang': 'en', 'q': query, 'src': 'spelling_expansion_revert_click'}), **kwargs)
		self._query = query
		self._cursor = cursor

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
			'simple_quoted_tweets': 'true',
			'q': self._query,
			'tweet_search_mode': 'live',
			'count': '100',
			'query_source': 'spelling_expansion_revert_click',
		}
		paginationParams = params.copy()
		paginationParams['cursor'] = None
		for d in (params, paginationParams):
			d['pc'] = '1'
			d['spelling_corrections'] = '1'
			d['ext'] = 'ext=mediaStats%2ChighlightedLabel'

		for obj in self._iter_api_data('https://api.twitter.com/2/search/adaptive.json', params, paginationParams):
			yield from self._instructions_to_tweets(obj)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('--cursor', metavar = 'CURSOR')
		subparser.add_argument('query', help = 'A Twitter search string')

	@classmethod
	def from_args(cls, args):
		return cls(args.query, cursor = args.cursor, retries = args.retries)


class TwitterUserScraper(TwitterSearchScraper):
	name = 'twitter-user'

	def __init__(self, username, **kwargs):
		if not self.is_valid_username(username):
			raise ValueError('Invalid username')
		super().__init__(f'from:{username}', **kwargs)
		self._username = username

	def _get_entity(self):
		self._ensure_guest_token(f'https://twitter.com/{self._username}')
		params = {'variables': json.dumps({'screen_name': self._username, 'withHighlightedLabel': True}, separators = (',', ':'))}
		obj = self._get_api_data('https://api.twitter.com/graphql/-xfUfZsnR_zqjFd-IfrN5A/UserByScreenName', params = urllib.parse.urlencode(params, quote_via=urllib.parse.quote))
		user = obj['data']['user']
		rawDescription = user['legacy']['description']
		description = self._render_text_with_urls(rawDescription, user['legacy']['entities']['description']['urls'])
		return User(
			username = user['legacy']['screen_name'],
			displayname = user['legacy']['name'],
			id = user['rest_id'],
			description = description,
			rawDescription = rawDescription,
			descriptionUrls = [{'text': x['display_url'], 'url': x['expanded_url'], 'tcourl': x['url'], 'indices': tuple(x['indices'])} for x in user['legacy']['entities']['description']['urls']],
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
		  )

	@staticmethod
	def is_valid_username(s):
		return 1 <= len(s) <= 15 and s.strip(string.ascii_letters + string.digits + '_') == ''

	@classmethod
	def setup_parser(cls, subparser):
		def username(s):
			if cls.is_valid_username(s):
				return s
			raise ValueError('Invalid username')

		subparser.add_argument('username', type = username, help = 'A Twitter username (without @)')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)


class TwitterProfileScraper(TwitterUserScraper):
	name = 'twitter-profile'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._baseUrl = f'https://twitter.com/{self._username}'

	def get_items(self):
		user = self.entity
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
			'simple_quoted_tweets': 'true',
			'include_tweet_replies': 'true',
			'userId': user.id,
			'count': '100',
		}
		paginationParams = params.copy()
		paginationParams['cursor'] = None
		for d in (params, paginationParams):
			d['ext'] = 'ext=mediaStats%2ChighlightedLabel'

		for obj in self._iter_api_data(f'https://api.twitter.com/2/timeline/profile/{user.id}.json', params, paginationParams):
			yield from self._instructions_to_tweets(obj)


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


class TwitterThreadScraper(TwitterOldDesignScraper):
	name = 'twitter-thread'

	def __init__(self, tweetID = None, **kwargs):
		if tweetID is not None and tweetID.strip('0123456789') != '':
			raise ValueError('Invalid tweet ID, must be numeric')
		super().__init__(**kwargs)
		self._tweetID = tweetID

	def get_items(self):
		headers = {'User-Agent': f'Opera/9.80 (Windows NT 6.1; WOW64) Presto/2.12.388 Version/12.18 Bot'}

		# Fetch the page of the last tweet in the thread
		r = self._get(f'https://twitter.com/user/status/{self._tweetID}', headers = headers)
		soup = bs4.BeautifulSoup(r.text, 'lxml')

		# Extract tweets on that page in the correct order; first, the tweet that was supplied, then the ancestors with pagination if necessary
		tweet = soup.find('div', 'ThreadedConversation--permalinkTweetWithAncestors')
		if tweet:
			tweet = tweet.find('div', 'tweet')
		if not tweet:
			logger.warning('Tweet does not exist, is not a thread, or does not have ancestors')
			return
		items = list(self._feed_to_items([tweet]))
		assert len(items) == 1
		yield items[0]
		username = items[0].username

		ancestors = soup.find('div', 'ThreadedConversation--ancestors')
		if not ancestors:
			logger.warning('Tweet does not have ancestors despite claiming to')
			return
		feed = reversed(ancestors.find_all('li', 'js-stream-item'))
		yield from self._feed_to_items(feed)

		# If necessary, iterate through pagination until reaching the initial tweet
		streamContainer = ancestors.find('div', 'stream-container')
		if not streamContainer.has_attr('data-max-position') or streamContainer['data-max-position'] == '':
			return
		minPosition = streamContainer['data-max-position']
		while True:
			r = self._get(
				f'https://twitter.com/i/{username}/conversation/{self._tweetID}?include_available_features=1&include_entities=1&min_position={minPosition}',
				headers = headers,
				responseOkCallback = self._check_json_callback
			  )

			obj = json.loads(r.text)
			soup = bs4.BeautifulSoup(obj['items_html'], 'lxml')
			feed = reversed(soup.find_all('li', 'js-stream-item'))
			yield from self._feed_to_items(feed)
			if not obj['has_more_items']:
				break
			minPosition = obj['max_position']

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('tweetID', help = 'A tweet ID of the last tweet in a thread')

	@classmethod
	def from_args(cls, args):
		return cls(tweetID = args.tweetID, retries = args.retries)


class TwitterListPostsScraper(TwitterSearchScraper):
	name = 'twitter-list-posts'

	def __init__(self, listName, **kwargs):
		super().__init__(f'list:{listName}', **kwargs)
		self._listName = listName

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('list', help = 'A Twitter list ID or a string of the form "username/listname" (replace spaces with dashes)')

	@classmethod
	def from_args(cls, args):
		return cls(args.list, retries = args.retries)
