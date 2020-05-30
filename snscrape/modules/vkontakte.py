import bs4
import datetime
import itertools
import logging
import snscrape.base
import typing
import urllib.parse


logger = logging.getLogger(__name__)


class VKontaktePost(typing.NamedTuple, snscrape.base.Item):
	url: str
	date: datetime.datetime
	content: str

	def __str__(self):
		return self.url


class VKontakteUserScraper(snscrape.base.Scraper):
	name = 'vkontakte-user'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username

	def _soup_to_items(self, soup, baseUrl):
		for post in soup.find_all('div', class_ = 'post'):
			dateSpan = post.find('div', class_ = 'post_date').find('span', class_ = 'rel_date')
			textDiv = post.find('div', class_ = 'wall_post_text')
			yield VKontaktePost(
			  url = urllib.parse.urljoin(baseUrl, post.find('a', class_ = 'post_link')['href']),
			  date = datetime.datetime.fromtimestamp(int(dateSpan['time']), datetime.timezone.utc) if 'time' in dateSpan else None,
			  content = textDiv.text if textDiv else None,
			 )

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0', 'Accept-Language': 'en-US,en;q=0.5'}
		baseUrl = f'https://vk.com/{self._username}'

		logger.info('Retrieving initial data')
		r = self._get(baseUrl, headers = headers)
		if r.status_code == 404:
			logger.warning('Wall does not exist')
			return
		elif r.status_code != 200:
			raise snscrape.base.ScraperException(f'Got status code {r.status_code}')

		# VK sends windows-1251-encoded data, but Requests's decoding doesn't seem to work correctly and causes lxml to choke, so we need to pass the binary content and the encoding explicitly.
		soup = bs4.BeautifulSoup(r.content, 'lxml', from_encoding = r.encoding)

		if soup.find('div', class_ = 'profile_closed_wall_dummy'):
			logger.warning('Private profile')
			return

		profileDeleted = soup.find('h5', class_ = 'profile_deleted_text')
		if profileDeleted:
			# Unclear what this state represents, so just log website text.
			logger.warning(profileDeleted.text)
			return

		newestPost = soup.find('div', class_ = 'post')
		if not newestPost:
			logger.info('Wall has no posts')
			return
		ownerID = newestPost.attrs['data-post-id'].split('_')[0]
		# If there is a pinned post, we need its ID for the pagination requests
		if 'post_fixed' in newestPost.attrs['class']:
			fixedPostID = newestPost.attrs['id'].split('_')[1]
		else:
			fixedPostID = ''

		yield from self._soup_to_items(soup, baseUrl)

		headers['X-Requested-With'] = 'XMLHttpRequest'
		for offset in itertools.count(start = 10, step = 10):
			logger.info('Retrieving next page')
			r = self._post(
			  'https://vk.com/al_wall.php',
			  data = [('act', 'get_wall'), ('al', 1), ('fixed', fixedPostID), ('offset', offset), ('onlyCache', 'false'), ('owner_id', ownerID), ('type', 'own'), ('wall_start_from', offset)],
			  headers = headers
			 )
			if r.status_code != 200:
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
			# Convert to JSON and read the HTML payload.  Note that this implicitly converts the data to a Python string (i.e., Unicode), away from a windows-1251-encoded bytes.
			posts = r.json()['payload'][1][0]
			if posts.startswith('<div class="page_block no_posts">'):
				# Reached the end
				break
			if not posts.startswith('<div id="post'):
				raise snscrape.base.ScraperException(f'Got an unknown response: {posts[:200]!r}...')
			soup = bs4.BeautifulSoup(posts, 'lxml')
			yield from self._soup_to_items(soup, baseUrl)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'A VK username')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)

