import json
import logging
import socialmediascraper.base


logger = logging.getLogger(__name__)


class InstagramUserScraper(socialmediascraper.base.Scraper):
	name = 'instagram-user'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username

	def _response_to_items(self, response, username):
		for node in response['user']['edge_owner_to_timeline_media']['edges']:
			code = node['node']['shortcode']
			yield socialmediascraper.base.URLItem(f'https://www.instagram.com/p/{code}/?taken-by={username}') #TODO: Do we want the taken-by parameter in here?

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

		logger.info('Retrieving initial data')
		r = self._get(f'https://www.instagram.com/{self._username}/?__a=1', headers = headers)
		if r.status_code == 404:
			logger.warning('User does not exist')
			return
		elif r.status_code != 200:
			logger.error(f'Got status code {r.status_code}')
			return
		response = json.loads(r.text)
		if response['graphql']['user']['edge_owner_to_timeline_media']['count'] == 0:
			logger.info('User has no posts')
			return
		if not response['graphql']['user']['edge_owner_to_timeline_media']['edges']:
			logger.warning('Private account')
			return
		userID = response['graphql']['user']['id']
		username = response['graphql']['user']['username'] # Might have different capitalisation than self._username
		yield from self._response_to_items(response['graphql'], username)
		if not response['graphql']['user']['edge_owner_to_timeline_media']['page_info']['has_next_page']:
			return
		endCursor = response['graphql']['user']['edge_owner_to_timeline_media']['page_info']['end_cursor']

		# Cf. https://stackoverflow.com/questions/49265339/instagram-a-1-url-doesnt-allow-max-id and https://github.com/rarcega/instagram-scraper
		while True:
			logger.info(f'Retrieving endCursor = {endCursor!r}')
			r = self._get(f'https://www.instagram.com/graphql/query/?query_hash=42323d64886122307be10013ad2dcc44&variables={{"id":"{userID}","first":12,"after":"{endCursor}"}}', headers = headers)

			if r.status_code != 200:
				logger.error(f'Got status code {r.status_code}')
				return

			response = json.loads(r.text)
			if not response['data']['user']['edge_owner_to_timeline_media']['edges']:
				return
			yield from self._response_to_items(response['data'], username)
			if not response['data']['user']['edge_owner_to_timeline_media']['page_info']['has_next_page']:
				return
			endCursor = response['data']['user']['edge_owner_to_timeline_media']['page_info']['end_cursor']

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'An Instagram username')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)
