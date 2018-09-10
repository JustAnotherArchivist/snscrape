import bs4
import json
import logging
import re
import snscrape.base
import urllib.parse


logger = logging.getLogger(__name__)


class FacebookUserScraper(snscrape.base.Scraper):
	name = 'facebook-user'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username

	def _soup_to_items(self, soup, username, baseUrl):
		yielded = set()
		for a in soup.find_all('a', href = re.compile(r'^/[^/]+/(posts|photos|videos)/[^/]*\d')):
			href = a.get('href')
			if href.startswith(f'/{username}/'):
				link = urllib.parse.urljoin(baseUrl, href)
				if link not in yielded:
					yield snscrape.base.URLItem(link)
					yielded.add(link)

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

		nextPageLinkPattern = re.compile(r'^/pages_reaction_units/more/\?page_id=')
		spuriousForLoopPattern = re.compile(r'^for \(;;\);')

		logger.info('Retrieving initial data')
		baseUrl = f'https://www.facebook.com/{self._username}/'
		r = self._get(baseUrl, headers = headers)
		if r.status_code == 404:
			logger.warning('User does not exist')
			return
		elif r.status_code != 200:
			logger.error('Got status code {r.status_code}')
			return
		soup = bs4.BeautifulSoup(r.text, 'lxml')
		username = re.sub(r'^https://www\.facebook\.com/([^/]+)/$', r'\1', soup.find('link').get('href')) # Canonical capitalisation
		baseUrl = f'https://www.facebook.com/{username}/'
		yield from self._soup_to_items(soup, username, baseUrl)
		nextPageLink = soup.find('a', ajaxify = nextPageLinkPattern)

		while nextPageLink:
			logger.info('Retrieving next page')

			# The web app sends a bunch of additional parameters. Most of them would be easy to add, but there's also __dyn, which is a compressed list of the "modules" loaded in the browser.
			# Reproducing that would be difficult to get right, especially as Facebook's codebase evolves, so it's just not sent at all here.
			r = self._get(urllib.parse.urljoin(baseUrl, nextPageLink.get('ajaxify')) + '&__a=1', headers = headers)
			if r.status_code != 200:
				logger.error(f'Got status code {r.status_code}')
				return
			response = json.loads(spuriousForLoopPattern.sub('', r.text))
			assert 'domops' in response
			assert len(response['domops']) == 1
			assert len(response['domops'][0]) == 4
			assert response['domops'][0][0] == 'replace', f'{response["domops"][0]} is not "replace"'
			assert response['domops'][0][1] == '#www_pages_reaction_see_more_unitwww_pages_home'
			assert response['domops'][0][2] == False
			assert '__html' in response['domops'][0][3]
			soup = bs4.BeautifulSoup(response['domops'][0][3]['__html'], 'lxml')
			yield from self._soup_to_items(soup, username, baseUrl)
			nextPageLink = soup.find('a', ajaxify = nextPageLinkPattern)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'A Facebook username or user ID')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)
