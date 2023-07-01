__all__ = ['InstagramPost', 'User', 'InstagramUserScraper', 'InstagramHashtagScraper', 'InstagramLocationScraper']


import dataclasses
import datetime
import hashlib
import json
import logging
import re
import snscrape.base
import snscrape.utils
import typing


_logger = logging.getLogger(__name__)


@dataclasses.dataclass
class InstagramPost(snscrape.base.Item):
	url: str
	date: datetime.datetime
	content: typing.Optional[str]
	thumbnailUrl: str
	displayUrl: str
	username: typing.Optional[str]
	likes: int
	comments: int
	commentsDisabled: bool
	isVideo: bool
	videoUrl: typing.Optional[str]
	id: str

	def __str__(self):
		return self.url


@dataclasses.dataclass
class User(snscrape.base.Item):
	username: str
	name: typing.Optional[str]
	followers: snscrape.base.IntWithGranularity
	following: snscrape.base.IntWithGranularity
	posts: snscrape.base.IntWithGranularity

	followersGranularity = snscrape.base._DeprecatedProperty('followersGranularity', lambda self: self.followers.granularity, 'followers.granularity')
	followingGranularity = snscrape.base._DeprecatedProperty('followingGranularity', lambda self: self.following.granularity, 'following.granularity')
	postsGranularity = snscrape.base._DeprecatedProperty('postsGranularity', lambda self: self.posts.granularity, 'posts.granularity')

	def __str__(self):
		return f'https://www.instagram.com/{self.username}/'


class _InstagramCommonScraper(snscrape.base.Scraper):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
		self._initialPage = None
		self._api_url = None

	def _response_to_items(self, response):
		for node in response[self._edgeXToMedia]['edges']:
			code = node['node']['shortcode']
			username = node['node']['owner']['username'] if 'username' in node['node']['owner'] else None
			url = f'https://www.instagram.com/p/{code}/'

			yield InstagramPost(
				url=url,
				date=datetime.datetime.fromtimestamp(node['node']['taken_at_timestamp'], datetime.timezone.utc),
				content=node['node']['edge_media_to_caption']['edges'][0]['node']['text'] if len(node['node']['edge_media_to_caption']['edges']) else None,
				thumbnailUrl=node['node']['thumbnail_src'],
				displayUrl=node['node']['display_url'],
				username=username,
				likes=node['node']['edge_media_preview_like']['count'],
				comments=node['node']['edge_media_to_comment']['count'],
				commentsDisabled=node['node']['comments_disabled'],
				isVideo=node['node']['is_video'],
				videoUrl=node['node']['video_url'] if 'video_url' in node['node'] else None,
				id=node['node']['id'],
			)

	def _initial_page(self):
		if self._initialPage is None:
			_logger.info('Retrieving initial data')
			r = self._get(self._initialUrl, headers = self._headers, responseOkCallback = self._check_initial_page_callback)
			if r.status_code not in (200, 404):
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
			elif r.url.startswith('https://www.instagram.com/accounts/login/'):
				raise snscrape.base.ScraperException('Redirected to login page')
			r = self._get(
				self._api_url,
				headers=self._headers,
				responseOkCallback=self._check_json_callback
			)
			self._initialPage = r

		return self._initialPage

	def _check_initial_page_callback(self, r):
		if r.status_code != 200:
			return True, None
		if (match := re.search(
				r'\\"csrf_token\\":\\"([\da-zA-Z]+)\\",',
				r.text)):
			_logger.debug('Found csrf token in HTML')
			self._headers['X-Csrftoken'] = match.group(1)
		if (match := re.search(
				r'"X-IG-App-ID":"(\d+)"',
				r.text)):
			_logger.debug('Found X-IG-App-ID token in HTML')
			self._headers['X-IG-App-ID'] = match.group(1)

		return True, None

	def _check_json_callback(self, r):
		if r.status_code != 200:
			return False, f'status code {r.status_code}'
		if r.url.startswith('https://www.instagram.com/accounts/login/'):
			raise snscrape.base.ScraperException('Redirected to login page')
		try:
			obj = json.loads(r.text)
		except json.JSONDecodeError as e:
			return False, f'invalid JSON ({e!r})'
		r._snscrape_json_obj = obj
		return True, None

	def get_items(self):
		r = self._initial_page()
		if r.status_code == 404:
			_logger.warning('Page does not exist')
			return
		response = r._snscrape_json_obj
		if response['data'][self._responseContainer][self._edgeXToMedia]['count'] == 0:
			_logger.info('Page has no posts')
			return
		if not response['data'][self._responseContainer][self._edgeXToMedia]['edges']:
			_logger.warning('Private account')
			return
		pageID = response['data'][self._responseContainer][self._pageIDKey]
		yield from self._response_to_items(response['data'][self._responseContainer])
		if not response['data'][self._responseContainer][self._edgeXToMedia]['page_info']['has_next_page']:
			return
		endCursor = response['data'][self._responseContainer][self._edgeXToMedia]['page_info']['end_cursor']

		headers = self._headers.copy()
		while True:
			_logger.info(f'Retrieving endCursor = {endCursor!r}')
			variables = self._variablesFormat.format(**locals())
			r = self._get(f'https://www.instagram.com/graphql/query/?query_hash={self._queryHash}&variables={variables}', headers = headers, responseOkCallback = self._check_json_callback)

			if r.status_code != 200:
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')

			response = r._snscrape_json_obj
			if not response['data'][self._responseContainer][self._edgeXToMedia]['edges']:
				return
			yield from self._response_to_items(response['data'][self._responseContainer])
			if not response['data'][self._responseContainer][self._edgeXToMedia]['page_info']['has_next_page']:
				return
			endCursor = response['data'][self._responseContainer][self._edgeXToMedia]['page_info']['end_cursor']


class InstagramUserScraper(_InstagramCommonScraper):
	name = 'instagram-user'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._initialUrl = f'https://www.instagram.com/{username}/'
		self._pageName = 'ProfilePage'
		self._responseContainer = 'user'
		self._edgeXToMedia = 'edge_owner_to_timeline_media'
		self._pageIDKey = 'id'
		self._queryHash = 'f2405b236d85e8296cf30347c9f08c2a'
		self._variablesFormat = '{{"id":"{pageID}","first":50,"after":"{endCursor}"}}'
		self._api_url = f'https://www.instagram.com/api/v1/users/web_profile_info/?username={username}'

	def _get_entity(self):
		r = self._initial_page()
		if r.status_code != 200:
			return
		if '<meta property="og:description" content="' not in r.text:
			return
		ogDescriptionContentPos = r.text.index('<meta property="og:description" content="') + len('<meta property="og:description" content="')
		ogDescription = r.text[ogDescriptionContentPos : r.text.index('"', ogDescriptionContentPos)]

		numPattern = r'\d+(?:\.\d+)?m|\d+(?:\.\d+)?k|\d+,\d+|\d+'
		ogDescriptionPattern = re.compile('^(' + numPattern + ') Followers, (' + numPattern + ') Following, (' + numPattern + r') Posts - See Instagram photos and videos from (?:(.*?) \(@([a-z0-9_.]+)\)|@([a-z0-9_-]+))$')
		m = ogDescriptionPattern.match(ogDescription)
		assert m, 'unexpected og:description format'

		def parse_num(s):
			if s.endswith('m'):
				return int(float(s[:-1].replace(',', '')) * 1e6), 10 ** (6 if '.' not in s else 6 - len(s[:-1].replace(',', '').split('.')[1]))
			elif s.endswith('k'):
				return int(float(s[:-1].replace(',', '')) * 1000), 10 ** (3 if '.' not in s else 3 - len(s[:-1].replace(',', '').split('.')[1]))
			else:
				return int(s.replace(',', '')), 1

		followers = snscrape.base.IntWithGranularity(*parse_num(m.group(1)))
		following = snscrape.base.IntWithGranularity(*parse_num(m.group(2)))
		posts = snscrape.base.IntWithGranularity(*parse_num(m.group(3)))
		return User(
			username = m.group(5) or m.group(6),
			name = m.group(4) or None,
			followers = followers,
			following = following,
			posts = posts,
		  )

	@classmethod
	def _cli_setup_parser(cls, subparser):
		subparser.add_argument('username', type = snscrape.utils.nonempty_string_arg('username'), help = 'An Instagram username (no leading @)')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, args.username)


class InstagramHashtagScraper(_InstagramCommonScraper):
	name = 'instagram-hashtag'

	def __init__(self, hashtag, **kwargs):
		super().__init__(**kwargs)
		self._initialUrl = f'https://www.instagram.com/explore/tags/{hashtag}/'
		self._pageName = 'TagPage'
		self._responseContainer = 'hashtag'
		self._edgeXToMedia = 'edge_hashtag_to_media'
		self._pageIDKey = 'name'
		self._queryHash = 'f92f56d47dc7a55b606908374b43a314'
		self._variablesFormat = '{{"tag_name":"{pageID}","first":50,"after":"{endCursor}"}}'
		self._api_url = f'https://www.instagram.com/api/v1/tags/logged_out_web_info/?tag_name={hashtag.lower()}'

	@classmethod
	def _cli_setup_parser(cls, subparser):
		subparser.add_argument('hashtag', type = snscrape.utils.nonempty_string_arg('hashtag'), help = 'An Instagram hashtag (no leading #)')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, args.hashtag)


class InstagramLocationScraper(_InstagramCommonScraper):
	name = 'instagram-location'

	def __init__(self, locationId, **kwargs):
		super().__init__(**kwargs)
		self._initialUrl = f'https://www.instagram.com/explore/locations/{locationId}/'
		self._pageName = 'LocationsPage'
		self._responseContainer = 'recent'
		self._edgeXToMedia = 'edge_location_to_media'
		self._pageIDKey = 'next_page'
		self._queryHash = '1b84447a4d8b6d6d0426fefb34514485'
		self._variablesFormat = '{{"id":"{pageID}","first":50,"after":"{endCursor}"}}'
		self._api_url = f"https://www.instagram.com/api/v1/locations/web_info/?location_id={locationId}"
		self._locationId = locationId

	@classmethod
	def _cli_setup_parser(cls, subparser):
		subparser.add_argument('locationid', help = 'An Instagram location ID', type = int)

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, args.locationid)

	def get_items(self):
		r = self._initial_page()
		if r.status_code == 404:
			_logger.warning('Page does not exist')
			return
		response = r._snscrape_json_obj
		if len(response['native_location_data'][self._responseContainer]['sections']) == 0:
			_logger.info('Page has no posts')
			return
		# pageID = response['native_location_data'][self._responseContainer][self._pageIDKey]
		yield from self._response_to_items(response['native_location_data'][self._responseContainer])

		# querying for more data returns the login page, so 1 set of images is all we get
		# if not response['native_location_data'][self._responseContainer]['more_available']:
		# 	return
		# endCursor = response['native_location_data'][self._responseContainer]['next_max_id']
		# headers = self._headers.copy()
		# headers['X-Requested-With'] = 'XMLHttpRequest'
		# # headers['X-Instagram-Ajax'] = 'XMLHttpRequest'
		# while True:
		# 	_logger.info(f'Retrieving endCursor = {endCursor!r}')
		# 	data = {
		# 		'surface': 'grid',
		# 		'tab': 'recent',
		# 		'max_id': endCursor,
		# 		'next_media_ids': [],
		# 		'page': pageID
		# 	}
		# 	r = self._post(
		# 		f'https://www.instagram.com/api/v1/locations/{self._locationId}/sections/',
		# 		headers=headers,
		# 		data=data,
		# 		responseOkCallback=self._check_json_callback
		# 	)
		#
		# 	if r.status_code != 200:
		# 		raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
		#
		# 	response = r._snscrape_json_obj
		# 	if not response['data']['location']:
		# 		return
		# 	yield from self._response_to_items(response['native_location_data'][self._responseContainer])
		# 	if not response['native_location_data'][self._responseContainer]['more_available']:
		# 		return
		# 	endCursor = response['native_location_data'][self._responseContainer]['next_max_id']

	def _response_to_items(self, response):
		for node in response['sections']:
			for media in node['layout_content']['medias']:
				code = media['media']['code']
				username = media['media']['user']['username'] if 'username' in media['media']['user'] else None
				url = f'https://www.instagram.com/p/{code}/'

				yield InstagramPost(
					url=url,
					date=datetime.datetime.fromtimestamp(media['media']['taken_at'], datetime.timezone.utc),
					content=media['media']['caption']['text'] if media['media']['caption'] else None,
					thumbnailUrl=media['media']['image_versions2']['candidates'][-1]['url'],
					displayUrl=media['media']['image_versions2']['candidates'][0]['url'],
					username=username,
					likes=media['media']['like_count'],
					comments=media['media']['comment_count'],
					commentsDisabled=False,
					isVideo=True if 'video_versions' in media['media'] else False,
					videoUrl=media['media']['video_versions'][0]['url'] if 'video_versions' in media['media'] else None,
					id=media['media']['id'],
				)
