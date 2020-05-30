import datetime
import hashlib
import json
import logging
import snscrape.base
import typing


logger = logging.getLogger(__name__)


class InstagramPost(typing.NamedTuple, snscrape.base.Item):
	cleanUrl: str
	dirtyUrl: str
	date: datetime.datetime
	content: str
	thumbnailUrl: str
	displayUrl: str
	username: str
	likes: int
	comments: int
	commentsDisabled: bool
	isVideo: bool

	def __str__(self):
		return self.cleanUrl


class InstagramCommonScraper(snscrape.base.Scraper):
	def __init__(self, mode, name, **kwargs):
		super().__init__(**kwargs)
		if mode not in ('User', 'Hashtag', 'Location'):
			raise ValueError('Invalid mode')
		self._mode = mode
		self._name = name

		if self._mode == 'User':
			self._initialUrl = f'https://www.instagram.com/{self._name}/'
			self._pageName = 'ProfilePage'
			self._responseContainer = 'user'
			self._edgeXToMedia = 'edge_owner_to_timeline_media'
			self._pageIDKey = 'id'
			self._queryHash = 'f2405b236d85e8296cf30347c9f08c2a'
			self._variablesFormat = '{{"id":"{pageID}","first":50,"after":"{endCursor}"}}'
		elif self._mode == 'Hashtag':
			self._initialUrl = f'https://www.instagram.com/explore/tags/{self._name}/'
			self._pageName = 'TagPage'
			self._responseContainer = 'hashtag'
			self._edgeXToMedia = 'edge_hashtag_to_media'
			self._pageIDKey = 'name'
			self._queryHash = 'f92f56d47dc7a55b606908374b43a314'
			self._variablesFormat = '{{"tag_name":"{pageID}","first":50,"after":"{endCursor}"}}'
		elif self._mode == 'Location':
			self._initialUrl = f'https://www.instagram.com/explore/locations/{self._name}/'
			self._pageName = 'LocationsPage'
			self._responseContainer = 'location'
			self._edgeXToMedia = 'edge_location_to_media'
			self._pageIDKey = 'id'
			self._queryHash = '1b84447a4d8b6d6d0426fefb34514485'
			self._variablesFormat = '{{"id":"{pageID}","first":50,"after":"{endCursor}"}}'

	def _response_to_items(self, response):
		for node in response[self._responseContainer][self._edgeXToMedia]['edges']:
			code = node['node']['shortcode']
			username = node['node']['owner']['username'] if 'username' in node['node']['owner'] else ''
			usernameQuery = '?taken-by=' + username
			cleanUrl = f'https://www.instagram.com/p/{code}/'
			yield InstagramPost(
			  cleanUrl = cleanUrl,
			  dirtyUrl = f'{cleanUrl}{usernameQuery}',
			  date = datetime.datetime.fromtimestamp(node['node']['taken_at_timestamp'], datetime.timezone.utc),
			  content = node['node']['edge_media_to_caption']['edges'][0]['node']['text'] if len(node['node']['edge_media_to_caption']['edges']) else None,
			  thumbnailUrl = node['node']['thumbnail_src'],
			  displayUrl = node['node']['display_url'],
			  username = username,
			  likes = node['node']['edge_media_preview_like']['count'],
			  comments = node['node']['edge_media_to_comment']['count'],
			  commentsDisabled = node['node']['comments_disabled'],
			  isVideo = node['node']['is_video'],
			 )

	def _check_initial_page_callback(self, r):
		if r.status_code != 200:
			return True, None
		jsonData = r.text.split('<script type="text/javascript">window._sharedData = ')[1].split(';</script>')[0] # May throw an IndexError if Instagram changes something again; we just let that bubble.
		try:
			obj = json.loads(jsonData)
		except json.JSONDecodeError:
			return False, 'invalid JSON'
		r._snscrape_json_obj = obj
		return True, None

	def _check_json_callback(self, r):
		if r.status_code != 200:
			return False, f'status code {r.status_code}'
		try:
			obj = json.loads(r.text)
		except json.JSONDecodeError as e:
			return False, f'invalid JSON ({e!r})'
		r._snscrape_json_obj = obj
		return True, None

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

		logger.info('Retrieving initial data')
		r = self._get(self._initialUrl, headers = headers, responseOkCallback = self._check_initial_page_callback)
		if r.status_code == 404:
			logger.warning(f'{self._mode} does not exist')
			return
		elif r.status_code != 200:
			raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
		elif r.url.startswith('https://www.instagram.com/accounts/login/'):
			raise snscrape.base.ScraperException('Redirected to login page')
		response = r._snscrape_json_obj
		rhxGis = response['rhx_gis'] if 'rhx_gis' in response else ''
		if response['entry_data'][self._pageName][0]['graphql'][self._responseContainer][self._edgeXToMedia]['count'] == 0:
			logger.info(f'{self._mode} has no posts')
			return
		if not response['entry_data'][self._pageName][0]['graphql'][self._responseContainer][self._edgeXToMedia]['edges']:
			logger.warning('Private account')
			return
		pageID = response['entry_data'][self._pageName][0]['graphql'][self._responseContainer][self._pageIDKey]
		yield from self._response_to_items(response['entry_data'][self._pageName][0]['graphql'])
		if not response['entry_data'][self._pageName][0]['graphql'][self._responseContainer][self._edgeXToMedia]['page_info']['has_next_page']:
			return
		endCursor = response['entry_data'][self._pageName][0]['graphql'][self._responseContainer][self._edgeXToMedia]['page_info']['end_cursor']

		while True:
			logger.info(f'Retrieving endCursor = {endCursor!r}')
			variables = self._variablesFormat.format(**locals())
			headers['X-Requested-With'] = 'XMLHttpRequest'
			headers['X-Instagram-GIS'] = hashlib.md5(f'{rhxGis}:{variables}'.encode('utf-8')).hexdigest()
			r = self._get(f'https://www.instagram.com/graphql/query/?query_hash={self._queryHash}&variables={variables}', headers = headers, responseOkCallback = self._check_json_callback)

			if r.status_code != 200:
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')

			response = r._snscrape_json_obj
			if not response['data'][self._responseContainer][self._edgeXToMedia]['edges']:
				return
			yield from self._response_to_items(response['data'])
			if not response['data'][self._responseContainer][self._edgeXToMedia]['page_info']['has_next_page']:
				return
			endCursor = response['data'][self._responseContainer][self._edgeXToMedia]['page_info']['end_cursor']


class InstagramUserScraper(InstagramCommonScraper):
	name = 'instagram-user'

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'An Instagram username (no leading @)')

	@classmethod
	def from_args(cls, args):
		return cls('User', args.username, retries = args.retries)


class InstagramHashtagScraper(InstagramCommonScraper):
	name = 'instagram-hashtag'

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('hashtag', help = 'An Instagram hashtag (no leading #)')

	@classmethod
	def from_args(cls, args):
		return cls('Hashtag', args.hashtag, retries = args.retries)


class InstagramLocationScraper(InstagramCommonScraper):
	name = 'instagram-location'

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('locationid', help = 'An Instagram location ID', type = int)

	@classmethod
	def from_args(cls, args):
		return cls('Location', args.locationid, retries = args.retries)
