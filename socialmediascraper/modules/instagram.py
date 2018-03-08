import json
import logging
import socialmediascraper.base


logger = logging.getLogger(__name__)


class InstagramUserScraper(socialmediascraper.base.Scraper):
	name = 'instagram-user'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username

	def _response_to_items(self, response):
		username = response['user']['username'] # Might have different capitalisation than self._username

		for node in response['user']['media']['nodes']:
			code = node['code']
			yield socialmediascraper.base.URLItem(f'https://www.instagram.com/p/{code}/?taken-by={username}') #TODO: Do we want the taken-by parameter in here?

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

		maxID = None

		while True:
			logger.info(f'Retrieving max_id = {maxID!r}')
			if maxID is None:
				url = f'https://www.instagram.com/{self._username}/?__a=1'
			else:
				url = f'https://www.instagram.com/{self._username}/?__a=1&max_id={maxID}'
			r = self._get(url, headers = headers)

			#TODO: Handle 404 (HTML)

			response = json.loads(r.text)
			if not response['user']['media']['nodes']:
				return
			yield from self._response_to_items(response)
			maxID = response['user']['media']['nodes'][-1]['id']

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'An Instagram username')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)
