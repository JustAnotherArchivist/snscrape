import datetime
import json
import logging
import snscrape.base
import time
import typing
import urllib.parse


logger = logging.getLogger(__name__)


class GabPost(typing.NamedTuple, snscrape.base.Item):
	url: str
	date: datetime.datetime
	content: str

	def __str__(self):
		return self.url


class GabUserCommonScraper(snscrape.base.Scraper):
	def __init__(self, mode, username, **kwargs):
		super().__init__(**kwargs)
		if mode not in ('posts', 'comments', 'media'):
			raise ValueError('Invalid mode')
		self._mode = mode
		self._username = username
		if mode == 'posts':
			self._baseUrl = f'https://gab.com/api/feed/{username}'
			self._beforeGlue = '?'
		elif mode == 'comments':
			self._baseUrl = f'https://gab.com/api/feed/{username}/comments?includes=post.conversation_parent'
			self._beforeGlue = '&'
		elif mode == 'media':
			self._baseUrl = f'https://gab.com/api/feed/{username}/media'
			self._beforeGlue = '?'

	def _response_to_items(self, response):
		yielded = set()
		for post in response['data']:
			if post['post']['id'] not in yielded:
				yield GabPost(
				  url = f'https://gab.com/{post["post"]["user"]["username"]}/posts/{post["post"]["id"]}',
				  date = datetime.datetime.strptime(post['post']['created_at'].replace('-', '', 2).replace(':', ''), '%Y%m%dT%H%M%S%z'),
				  content = post['post']['body'],
				 )
				yielded.add(post['post']['id'])

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0', 'Accept-Language': 'en-US,en;q=0.5'}

		logger.info('Retrieving initial data')
		r = self._get(self._baseUrl, headers = headers)
		if r.status_code == 404:
			logger.error('User does not exist')
			return
		elif r.status_code != 200:
			logger.error(f'Got status code {r.status_code}')
			return

		response = json.loads(r.text)
		if not response['data']:
			logger.error('User has no posts')
			return
		yield from self._response_to_items(response)
		if self._mode == 'posts':
			before = response['data'][-1]['published_at']
		elif self._mode in ('comments', 'media'):
			before = 30

		while True:
			logger.info('Retrieving next page')
			r = self._get(f'{self._baseUrl}{self._beforeGlue}before={before}', headers = headers)
			if r.status_code != 200:
				logger.error(f'Got status code {r.status_code}')
				return
			response = json.loads(r.text)
			yield from self._response_to_items(response)
			if response['no-more'] or not response['data']:
				# Last page
				return
			if self._mode == 'posts':
				before = response['data'][-1]['published_at']
			elif self._mode in ('comments', 'media'):
				before += 30
			time.sleep(1) # Gab's API is pretty quick but doesn't like being hammered...

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'A Gab username')


class GabUserPostsScraper(GabUserCommonScraper):
	name = 'gab-user'

	@classmethod
	def from_args(cls, args):
		return cls('posts', args.username, retries = args.retries)


class GabUserCommentsScraper(GabUserCommonScraper):
	name = 'gab-user-comments'

	@classmethod
	def from_args(cls, args):
		return cls('comments', args.username, retries = args.retries)


class GabUserMediaScraper(GabUserCommonScraper):
	name = 'gab-user-media'

	@classmethod
	def from_args(cls, args):
		return cls('media', args.username, retries = args.retries)
