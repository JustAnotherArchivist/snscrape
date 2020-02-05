import bs4
import datetime
import json
import logging
import re
import snscrape.base
import typing
import urllib.parse


logger = logging.getLogger(__name__)


class FacebookPost(typing.NamedTuple, snscrape.base.Item):
	cleanUrl: str
	dirtyUrl: str
	date: datetime.datetime
	content: typing.Optional[str]
	outlinks: list
	outlinksss: str

	def __str__(self):
		return self.cleanUrl


class FacebookCommonScraper(snscrape.base.Scraper):
	def _clean_url(self, dirtyUrl):
		u = urllib.parse.urlparse(dirtyUrl)
		if u.path == '/permalink.php':
			# Retain only story_fbid and id parameters
			q = urllib.parse.parse_qs(u.query)
			clean = (u.scheme, u.netloc, u.path, urllib.parse.urlencode((('story_fbid', q['story_fbid'][0]), ('id', q['id'][0]))), '')
		elif u.path == '/photo.php':
			# Retain only the fbid parameter
			q = urllib.parse.parse_qs(u.query)
			clean = (u.scheme, u.netloc, u.path, urllib.parse.urlencode((('fbid', q['fbid'][0]),)), '')
		elif u.path == '/media/set/':
			# Retain only the set parameter and try to shorten it to the minimum
			q = urllib.parse.parse_qs(u.query)
			setVal = q['set'][0]
			if setVal.rstrip('0123456789').endswith('.a.'):
				setVal = f'a.{setVal.rsplit(".", 1)[1]}'
			clean = (u.scheme, u.netloc, u.path, urllib.parse.urlencode((('set', setVal),)), '')
		elif u.path.split('/')[2] == 'posts' or u.path.startswith('/events/') or u.path.startswith('/notes/'):
			# No manipulation of the path needed, but strip the query string
			clean = (u.scheme, u.netloc, u.path, '', '')
		elif u.path.split('/')[2] in ('photos', 'videos'):
			# Path: "/" username or ID "/" photos or videos "/" crap "/" ID of photo or video "/"
			# But to be safe, also handle URLs that don't have that crap correctly.
			if u.path.count('/') == 4:
				clean = (u.scheme, u.netloc, u.path, '', '')
			elif u.path.count('/') == 5:
				# Strip out the third path component
				pathcomps = u.path.split('/')
				pathcomps.pop(3) # Don't forget about the empty string at the beginning!
				clean = (u.scheme, u.netloc, '/'.join(pathcomps), '', '')
			else:
				return dirtyUrl
		else:
			# If we don't recognise the URL, just return the original one.
			return dirtyUrl
		return urllib.parse.urlunsplit(clean)

	def _is_odd_link(self, href, entryText, mode):
		# Returns (isOddLink: bool, warn: bool|None)
		if mode == 'user':
			if not any(x in href for x in ('/posts/', '/photos/', '/videos/', '/permalink.php?', '/events/', '/notes/', '/photo.php?', '/media/set/')):
				if href == '#' and 'new photo' in entryText and 'to the album' in entryText:
					# Don't print a warning if it's a "User added 5 new photos to the album"-type entry, which doesn't have a permalink.
					return True, False
				elif href.startswith('/business/help/788160621327601/?'):
					# Skip the help article about branded content
					return True, False
				else:
					return True, True
			return False, None
		elif mode == 'group':
			if not re.match(r'^/groups/[^/]+/permalink/\d+/(\?|$)', href):
				return True, True
			return False, None

	def _soup_to_items(self, soup, baseUrl, mode):
		cleanUrl = None # Value from previous iteration is used for warning on link-less entries
		for entry in soup.find_all('div', class_ = '_5pcr'): # also class 'fbUserContent' in 2017 and 'userContentWrapper' in 2019
			entryA = entry.find('a', class_ = '_5pcq') # There can be more than one, e.g. when a post is shared by another user, but the first one is always the one of this entry.
			mediaSetA = entry.find('a', class_ = '_17z-')
			if not mediaSetA and not entryA:
				logger.warning(f'Ignoring link-less entry after {cleanUrl}: {entry.text!r}')
				continue
			if mediaSetA and (not entryA or entryA['href'] == '#'):
				href = mediaSetA['href']
			elif entryA:
				href = entryA['href']
			oddLink, warn = self._is_odd_link(href, entry.text, mode)
			if oddLink:
				if warn:
					logger.warning(f'Ignoring odd link: {href}')
				continue
			dirtyUrl = urllib.parse.urljoin(baseUrl, href)
			cleanUrl = self._clean_url(dirtyUrl)
			date = datetime.datetime.fromtimestamp(int(entry.find('abbr', class_ = '_5ptz')['data-utime']), datetime.timezone.utc)
			contentDiv = entry.find('div', class_ = '_5pbx')
			if contentDiv:
				content = contentDiv.text
			else:
				content = None
			outlinks = []
			for a in entry.find_all('a'):
				if not a.has_attr('href'):
					continue
				href = a.get('href')
				if not href.startswith('https://l.facebook.com/l.php?'):
					continue
				query = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
				if 'u' not in query or len(query['u']) != 1:
					logger.warning(f'Ignoring odd outlink: {href}')
					continue
				outlink = query['u'][0]
				if outlink.startswith('http://') or outlink.startswith('https://') and outlink not in outlinks:
					outlinks.append(outlink)
			yield FacebookPost(cleanUrl = cleanUrl, dirtyUrl = dirtyUrl, date = date, content = content, outlinks = outlinks, outlinksss = ' '.join(outlinks))


class FacebookUserScraper(FacebookCommonScraper):
	name = 'facebook-user'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36', 'Accept-Language': 'en-US,en;q=0.5'}

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
		yield from self._soup_to_items(soup, baseUrl, 'user')
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
			yield from self._soup_to_items(soup, baseUrl, 'user')
			nextPageLink = soup.find('a', ajaxify = nextPageLinkPattern)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'A Facebook username or user ID')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)


class FacebookGroupScraper(FacebookCommonScraper):
	name = 'facebook-group'

	def __init__(self, group, **kwargs):
		super().__init__(**kwargs)
		self._group = group

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36', 'Accept-Language': 'en-US,en;q=0.5'}

		pageletDataPattern = re.compile(r'"GroupEntstreamPagelet",\{.*?\}(?=,\{)')
		pageletDataPrefixLength = len('"GroupEntstreamPagelet",')
		spuriousForLoopPattern = re.compile(r'^for \(;;\);')

		baseUrl = f'https://www.facebook.com/groups/{self._group}/'
		r = self._get(baseUrl, headers = headers)
		if r.status_code == 404:
			logger.warning('Group does not exist')
			return
		elif r.status_code != 200:
			logger.error('Got status code {r.status_code}')
			return

		if 'content:{pagelet_group_mall:{container_id:"' not in r.text:
			logger.error('Code container ID marker not found (does the group exist?)')
			return

		soup = bs4.BeautifulSoup(r.text, 'lxml')

		# Posts are inside an HTML comment in two code tags with IDs listed in JS...
		for codeContainerIdStart in ('content:{pagelet_group_mall:{container_id:"', 'content:{group_mall_after_tti:{container_id:"'):
			codeContainerIdPos = r.text.index(codeContainerIdStart) + len(codeContainerIdStart)
			codeContainerId = r.text[codeContainerIdPos : r.text.index('"', codeContainerIdPos)]
			codeContainer = soup.find('code', id = codeContainerId)
			if not codeContainer:
				raise RuntimeError('Code container not found')
			if type(codeContainer.string) is not bs4.element.Comment:
				raise RuntimeError('Code container does not contain a comment')
			codeSoup = bs4.BeautifulSoup(codeContainer.string, 'lxml')
			yield from self._soup_to_items(codeSoup, baseUrl, 'group')

		# Pagination
		data = pageletDataPattern.search(r.text).group(0)[pageletDataPrefixLength:]
		while True:
			# As on the user profile pages, the web app sends a lot of additional parameters, but those all seem to be unnecessary (although some change the response format, e.g. from JSON to HTML)
			r = self._get(
				f'https://www.facebook.com/ajax/pagelet/generic.php/GroupEntstreamPagelet',
				params = {'data': data, '__a': 1},
				headers = headers,
			  )
			if r.status_code != 200:
				raise RuntimeError(f'Got status code {r.status_code}')
			obj = json.loads(spuriousForLoopPattern.sub('', r.text))
			if obj['payload'] == '':
				# End of pagination
				break
			soup = bs4.BeautifulSoup(obj['payload'], 'lxml')
			yield from self._soup_to_items(soup, baseUrl, 'group')
			data = pageletDataPattern.search(r.text).group(0)[pageletDataPrefixLength:]

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('group', help = 'A group name or ID')

	@classmethod
	def from_args(cls, args):
		return cls(args.group, retries = args.retries)
