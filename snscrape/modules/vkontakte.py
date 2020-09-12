import bs4
import collections
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


class User(typing.NamedTuple, snscrape.base.Entity):
	username: str
	name: str
	verified: bool
	description: typing.Optional[str] = None
	websites: typing.Optional[typing.List[str]] = None
	followers: typing.Optional[int] = None
	followersGranularity: typing.Optional[snscrape.base.Granularity] = None
	posts: typing.Optional[int] = None
	postsGranularity: typing.Optional[snscrape.base.Granularity] = None
	photos: typing.Optional[int] = None
	photosGranularity: typing.Optional[snscrape.base.Granularity] = None
	tags: typing.Optional[int] = None
	tagsGranularity: typing.Optional[snscrape.base.Granularity] = None
	following: typing.Optional[int] = None
	followingGranularity: typing.Optional[snscrape.base.Granularity] = None

	def __str__(self):
		return f'https://vk.com/{self.username}'


class VKontakteUserScraper(snscrape.base.Scraper):
	name = 'vkontakte-user'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username
		self._baseUrl = f'https://vk.com/{self._username}'
		self._headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0', 'Accept-Language': 'en-US,en;q=0.5'}
		self._initialPage = None
		self._initialPageSoup = None

	def _post_div_to_item(self, post):
		url = urllib.parse.urljoin(self._baseUrl, post.find('a', class_ = 'post_link')['href'])
		assert url.startswith('https://vk.com/wall') and '_' in url and url[-1] != '_' and url.rsplit('_', 1)[1].strip('0123456789') == ''
		dateSpan = post.find('div', class_ = 'post_date').find('span', class_ = 'rel_date')
		textDiv = post.find('div', class_ = 'wall_post_text')
		return VKontaktePost(
		  url = url,
		  date = datetime.datetime.fromtimestamp(int(dateSpan['time']), datetime.timezone.utc) if 'time' in dateSpan else None,
		  content = textDiv.text if textDiv else None,
		 )

	def _soup_to_items(self, soup):
		for post in soup.find_all('div', class_ = 'post'):
			yield self._post_div_to_item(post)

	def _initial_page(self):
		if self._initialPage is None:
			logger.info('Retrieving initial data')
			r = self._get(self._baseUrl, headers = self._headers)
			if r.status_code not in (200, 404):
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
			# VK sends windows-1251-encoded data, but Requests's decoding doesn't seem to work correctly and causes lxml to choke, so we need to pass the binary content and the encoding explicitly.
			self._initialPage, self._initialPageSoup = r, bs4.BeautifulSoup(r.content, 'lxml', from_encoding = r.encoding)
		return self._initialPage, self._initialPageSoup

	def get_items(self):
		r, soup = self._initial_page()
		if r.status_code == 404:
			logger.warning('Wall does not exist')
			return

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
		# If there is a pinned post, we need its ID for the pagination requests; we also need to keep the post around so it can be inserted into the stream at the right point
		if 'post_fixed' in newestPost.attrs['class']:
			fixedPostID = int(newestPost.attrs['id'].split('_')[1])
		else:
			fixedPostID = ''

		last1000PostIDs = collections.deque(maxlen = 1000)

		def _process_soup(soup):
			nonlocal last1000PostIDs
			for item in self._soup_to_items(soup):
				postID = int(item.url.rsplit('_', 1)[1])
				if postID not in last1000PostIDs:
					yield item
					last1000PostIDs.append(postID)

		yield from _process_soup(soup)

		lastWorkingOffset = 0
		for offset in itertools.count(start = 10, step = 10):
			posts = self._get_wall_offset(fixedPostID, ownerID, offset)
			if posts.startswith('<div class="page_block no_posts">'):
				# Reached the end
				break
			if not posts.startswith('<div id="post'):
				if posts == '"\\/blank.php?block=119910902"':
					logger.warning(f'Encountered geoblock on offset {offset}, trying to work around the block but might be missing content')
					for geoblockOffset in range(lastWorkingOffset + 1, offset + 10):
						geoPosts = self._get_wall_offset(fixedPostID, ownerID, geoblockOffset)
						if geoPosts.startswith('<div class="page_block no_posts">'):
							# No breaking the outer loop, it'll just make one extra request and exit as well
							break
						if not geoPosts.startswith('<div id="post'):
							if geoPosts == '"\\/blank.php?block=119910902"':
								continue
							raise snscrape.base.ScraperException(f'Got an unknown response: {geoPosts[:200]!r}...')
						yield from _process_soup(soup = bs4.BeautifulSoup(geoPosts, 'lxml'))
					continue
				raise snscrape.base.ScraperException(f'Got an unknown response: {posts[:200]!r}...')
			lastWorkingOffset = offset
			soup = bs4.BeautifulSoup(posts, 'lxml')
			yield from _process_soup(soup)

	def _get_wall_offset(self, fixedPostID, ownerID, offset):
		headers = self._headers.copy()
		headers['X-Requested-With'] = 'XMLHttpRequest'
		logger.info(f'Retrieving page offset {offset}')
		r = self._post(
		  'https://vk.com/al_wall.php',
		  data = [('act', 'get_wall'), ('al', 1), ('fixed', fixedPostID), ('offset', offset), ('onlyCache', 'false'), ('owner_id', ownerID), ('type', 'own'), ('wall_start_from', offset)],
		  headers = headers
		 )
		if r.status_code != 200:
			raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
		# Convert to JSON and read the HTML payload.  Note that this implicitly converts the data to a Python string (i.e., Unicode), away from a windows-1251-encoded bytes.
		posts = r.json()['payload'][1][0]
		return posts

	def _get_entity(self):
		r, soup = self._initial_page()
		if r.status_code != 200:
			return
		kwargs = {}
		kwargs['username'] = r.url.rsplit('/', 1)[1]
		nameH1 = soup.find('h1', class_ = 'page_name')
		kwargs['name'] = nameH1.text
		kwargs['verified'] = bool(nameH1.find('div', class_ = 'page_verified'))

		descriptionDiv = soup.find('div', id = 'page_current_info')
		if descriptionDiv:
			kwargs['description'] = descriptionDiv.text

		infoDiv = soup.find('div', id = 'page_info_wrap')
		if infoDiv:
			websites = []
			for rowDiv in infoDiv.find_all('div', class_ = ['profile_info_row', 'group_info_row']):
				if 'profile_info_row' in rowDiv['class']:
					labelDiv = rowDiv.find('div', class_ = 'fl_l')
					if not labelDiv or labelDiv.text != 'Website:':
						continue
				else: # group_info_row
					if rowDiv['title'] == 'Description':
						kwargs['description'] = rowDiv.text
					if rowDiv['title'] != 'Website':
						continue
				for a in rowDiv.find_all('a'):
					if not a['href'].startswith('/away.php?to='):
						logger.warning(f'Skipping odd website link: {a["href"]!r}')
						continue
					websites.append(urllib.parse.unquote(a['href'].split('=', 1)[1].split('&', 1)[0]))
			if websites:
				kwargs['websites'] = websites

		def parse_num(s):
			if s.endswith('K'):
				return int(s[:-1]) * 1000, 1000
			else:
				return int(s.replace(',', '')), 1

		countsDiv = soup.find('div', class_ = 'counts_module')
		if countsDiv:
			for a in countsDiv.find_all('a', class_ = 'page_counter'):
				count, granularity = parse_num(a.find('div', class_ = 'count').text)
				label = a.find('div', class_ = 'label').text
				if label in ('follower', 'post', 'photo', 'tag'):
					label = f'{label}s'
				if label in ('followers', 'posts', 'photos', 'tags'):
					kwargs[label], kwargs[f'{label}Granularity'] = count, granularity

		idolsDiv = soup.find('div', id = 'profile_idols')
		if idolsDiv:
			topDiv = idolsDiv.find('div', class_ = 'header_top')
			if topDiv and topDiv.find('span', class_ = 'header_label').text == 'Following':
				kwargs['following'], kwargs['followingGranularity'] = parse_num(topDiv.find('span', class_ = 'header_count').text)

		# On public pages, this is where followers are listed
		followersDiv = soup.find('div', id = 'public_followers')
		if followersDiv:
			topDiv = followersDiv.find('div', class_ = 'header_top')
			if topDiv and topDiv.find('span', class_ = 'header_label').text == 'Followers':
				kwargs['followers'], kwargs['followersGranularity'] = parse_num(topDiv.find('span', class_ = 'header_count').text)

		return User(**kwargs)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'A VK username')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)

