import bs4
import datetime
import json
import random
import logging
import re
import snscrape.base
import time
import typing
import urllib.parse


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


class Account(typing.NamedTuple, snscrape.base.Item):
	username: str

	@property
	def url(self):
		return f'https://twitter.com/{self.username}'

	def __str__(self):
		return self.url


class TwitterCommonScraper(snscrape.base.Scraper):
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


class TwitterSearchScraper(TwitterCommonScraper):
	name = 'twitter-search'

	def __init__(self, query, cursor = None, **kwargs):
		super().__init__(**kwargs)
		self._query = query
		self._cursor = cursor
		self._userAgent = f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.{random.randint(0, 9999)} Safari/537.{random.randint(0, 99)}'
		self._baseUrl = 'https://twitter.com/search?' + urllib.parse.urlencode({'f': 'live', 'lang': 'en', 'q': self._query, 'src': 'spelling_expansion_revert_click'})

	def _get_guest_token(self):
		logger.info(f'Retrieving guest token from search page')
		r = self._get(self._baseUrl, headers = {'User-Agent': self._userAgent})
		match = re.search(r'document\.cookie = decodeURIComponent\("gt=(\d+); Max-Age=10800; Domain=\.twitter\.com; Path=/; Secure"\);', r.text)
		if match:
			logger.debug('Found guest token in HTML')
			return match.group(1)
		if 'gt' in r.cookies:
			logger.debug('Found guest token in cookies')
			return r.cookies['gt']
		raise snscrape.base.ScraperException('Unable to find guest token')

	def _check_scroll_response(self, r):
		if r.status_code == 429:
			# Accept a 429 response as "valid" to prevent retries; handled explicitly in get_items
			return True, None
		if r.headers.get('content-type') != 'application/json;charset=utf-8':
			return False, f'content type is not JSON'
		if r.status_code != 200:
			return False, f'non-200 status code'
		return True, None

	def get_items(self):
		headers = {
			'User-Agent': self._userAgent,
			'Authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
			'Referer': self._baseUrl,
		}
		guestToken = None
		cursor = self._cursor
		while True:
			if not guestToken:
				guestToken = self._get_guest_token()
				self._session.cookies.set('gt', guestToken, domain = '.twitter.com', path = '/', secure = True, expires = time.time() + 10800)
				headers['x-guest-token'] = guestToken

			logger.info(f'Retrieving scroll page {cursor}')
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
				'include_composer_source': 'true',
				'include_ext_alt_text': 'true',
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
			if cursor:
				params['cursor'] = cursor
			params['pc'] = '1'
			params['spelling_corrections'] = '1'
			params['ext'] = 'mediaStats%2CcameraMoment'
			r = self._get('https://api.twitter.com/2/search/adaptive.json', params = params, headers = headers, responseOkCallback = self._check_scroll_response)
			if r.status_code == 429:
				guestToken = None
				del self._session.cookies['gt']
				del headers['x-guest-token']
				continue
			try:
				obj = r.json()
			except json.JSONDecodeError as e:
				raise snscrape.base.ScraperException('Received invalid JSON from Twitter') from e

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
					if entry['entryId'].startswith('sq-I-t-'):
						if 'tweet' in entry['content']['item']['content']:
							tweet = obj['globalObjects']['tweets'][entry['content']['item']['content']['tweet']['id']]
						elif 'tombstone' in entry['content']['item']['content'] and 'tweet' in entry['content']['item']['content']['tombstone']:
							tweet = obj['globalObjects']['tweets'][entry['content']['item']['content']['tombstone']['tweet']['id']]
						else:
							raise snscrape.base.ScraperException(f'Unable to handle entry {entry["entryId"]!r}')
						tweetID = tweet['id']
						content = tweet['full_text']
						username = obj['globalObjects']['users'][tweet['user_id_str']]['screen_name']
						date = datetime.datetime.strptime(tweet['created_at'], '%a %b %d %H:%M:%S +0000 %Y').replace(tzinfo = datetime.timezone.utc)
						outlinks = [u['expanded_url'] for u in tweet['entities']['urls']]
						tcooutlinks = [u['url'] for u in tweet['entities']['urls']]
						url = f'https://twitter.com/{username}/status/{tweetID}'
						yield Tweet(url, date, content, tweetID, username, outlinks, ' '.join(outlinks), tcooutlinks, ' '.join(tcooutlinks))
					elif entry['entryId'] == 'sq-cursor-bottom':
						newCursor = entry['content']['operation']['cursor']['value']
			if not newCursor or newCursor == cursor:
				# End of pagination
				break
			cursor = newCursor

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


class TwitterThreadScraper(TwitterCommonScraper):
	name = 'twitter-thread'

	def __init__(self, tweetID = None, **kwargs):
		if tweetID is not None and tweetID.strip('0123456789') != '':
			raise ValueError('Invalid tweet ID, must be numeric')
		super().__init__(**kwargs)
		self._tweetID = tweetID

	def get_items(self):
		headers = {'User-Agent': f'Opera/9.80 (Windows NT 6.1; WOW64) Presto/2.12.388 Version/12.18'}

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
		subparser.add_argument('list', help = 'A Twitter list, formatted as "username/listname"')

	@classmethod
	def from_args(cls, args):
		return cls(args.list, retries = args.retries)


class TwitterListMembersScraper(TwitterCommonScraper):
	name = 'twitter-list-members'

	def __init__(self, listName, **kwargs):
		super().__init__(**kwargs)
		self._user, self._list = listName.split('/')

	def get_items(self):
		headers = {'User-Agent': f'Opera/9.80 (Windows NT 6.1; WOW64) Presto/2.12.388 Version/12.18'}

		baseUrl = f'https://twitter.com/{self._user}/lists/{self._list}/members'
		r = self._get(baseUrl, headers = headers)
		if r.status_code != 200:
			logger.warning('List not found')
			return
		soup = bs4.BeautifulSoup(r.text, 'lxml')
		container = soup.find('div', 'stream-container')
		if not container:
			raise snscrape.base.ScraperException('Unable to find container')
		items = container.find_all('li', 'js-stream-item')
		if not items:
			logger.warning('Empty list')
			return
		for item in items:
			yield Account(username = item.find('div', 'account')['data-screen-name'])

		if not container.has_attr('data-min-position') or container['data-min-position'] == '':
			return
		maxPosition = container['data-min-position']
		while True:
			r = self._get(
				f'{baseUrl}/timeline?include_available_features=1&include_entities=1&max_position={maxPosition}&reset_error_state=false',
				headers = headers,
				responseOkCallback = self._check_json_callback
			  )
			obj = json.loads(r.text)
			soup = bs4.BeautifulSoup(obj['items_html'], 'lxml')
			items = soup.find_all('li', 'js-stream-item')
			for item in items:
				yield Account(username = item.find('div', 'account')['data-screen-name'])
			if not obj['has_more_items']:
				break
			maxPosition = obj['min_position']

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('list', help = 'A Twitter list, formatted as "username/listname"')

	@classmethod
	def from_args(cls, args):
		return cls(args.list, retries = args.retries)
