import hashlib
import json
import logging
import snscrape.base


logger = logging.getLogger(__name__)


class InstagramUserScraper(snscrape.base.Scraper):
	name = 'instagram-user'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username

	def _response_to_items(self, response, username):
		for node in response['user']['edge_owner_to_timeline_media']['edges']:
			code = node['node']['shortcode']
			yield snscrape.base.URLItem(f'https://www.instagram.com/p/{code}/?taken-by={username}') #TODO: Do we want the taken-by parameter in here?

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

		logger.info('Retrieving initial data')
		r = self._get(f'https://www.instagram.com/{self._username}/', headers = headers)
		if r.status_code == 404:
			logger.warning('User does not exist')
			return
		elif r.status_code != 200:
			logger.error(f'Got status code {r.status_code}')
			return
		jsonData = r.text.split('<script type="text/javascript">window._sharedData = ')[1].split(';</script>')[0] # May throw an IndexError if Instagram changes something again; we just let that bubble.
		response = json.loads(jsonData)
		rhxGis = response['rhx_gis']
		if response['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media']['count'] == 0:
			logger.info('User has no posts')
			return
		if not response['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media']['edges']:
			logger.warning('Private account')
			return
		userID = response['entry_data']['ProfilePage'][0]['graphql']['user']['id']
		username = response['entry_data']['ProfilePage'][0]['graphql']['user']['username'] # Might have different capitalisation than self._username
		yield from self._response_to_items(response['entry_data']['ProfilePage'][0]['graphql'], username)
		if not response['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media']['page_info']['has_next_page']:
			return
		endCursor = response['entry_data']['ProfilePage'][0]['graphql']['user']['edge_owner_to_timeline_media']['page_info']['end_cursor']

		while True:
			logger.info(f'Retrieving endCursor = {endCursor!r}')
			variables = f'{{"id":"{userID}","first":50,"after":"{endCursor}"}}'
			headers['X-Requested-With'] = 'XMLHttpRequest'
			headers['X-Instagram-GIS'] = hashlib.md5(f'{rhxGis}:{variables}'.encode('utf-8')).hexdigest()
			r = self._get(f'https://www.instagram.com/graphql/query/?query_hash=42323d64886122307be10013ad2dcc44&variables={variables}', headers = headers)

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
