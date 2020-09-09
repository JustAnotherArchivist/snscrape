import bs4
import datetime
import logging
import snscrape.base
import typing
import urllib.parse


logger = logging.getLogger(__name__)


class TelegramPost(typing.NamedTuple, snscrape.base.Item):
	url: str
	date: datetime.datetime
	content: str
	outlinks: list
	outlinksss: str

	def __str__(self):
		return self.url


class Channel(typing.NamedTuple, snscrape.base.Entity):
	username: str
	title: str
	verified: bool
	photo: str
	description: typing.Optional[str] = None
	members: typing.Optional[int] = None
	photos: typing.Optional[int] = None
	photosGranularity: typing.Optional[snscrape.base.Granularity] = None
	videos: typing.Optional[int] = None
	videosGranularity: typing.Optional[snscrape.base.Granularity] = None
	links: typing.Optional[int] = None
	linksGranularity: typing.Optional[snscrape.base.Granularity] = None
	files: typing.Optional[int] = None
	filesGranularity: typing.Optional[snscrape.base.Granularity] = None

	def __str__(self):
		return f'https://t.me/s/{self.username}'


class TelegramChannelScraper(snscrape.base.Scraper):
	name = 'telegram-channel'

	def __init__(self, name, **kwargs):
		super().__init__(**kwargs)
		self._name = name
		self._headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'}
		self._initialPage = None
		self._initialPageSoup = None

	def _initial_page(self):
		if self._initialPage is None:
			r = self._get(f'https://t.me/s/{self._name}', headers = self._headers)
			if r.status_code != 200:
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
			self._initialPage, self._initialPageSoup = r, bs4.BeautifulSoup(r.text, 'lxml')
		return self._initialPage, self._initialPageSoup

	def _soup_to_items(self, soup, pageUrl):
		posts = soup.find_all('div', attrs = {'class': 'tgme_widget_message', 'data-post': True})
		for post in reversed(posts):
			date = datetime.datetime.strptime(post.find('div', class_ = 'tgme_widget_message_footer').find('a', class_ = 'tgme_widget_message_date').find('time', datetime = True)['datetime'].replace('-', '', 2).replace(':', ''), '%Y%m%dT%H%M%S%z')
			message = post.find('div', class_ = 'tgme_widget_message_text')
			if message:
				content = message.text
				outlinks = [urllib.parse.urljoin(pageUrl, link['href']) for link in post.find_all('a') if not link.text.startswith('@') and link['href'].startswith('https://t.me/')]
				outlinksss = ' '.join(outlinks)
			else:
				content = None
				outlinks = []
				outlinksss = ''
			yield TelegramPost(url = f'https://t.me/s/{post["data-post"]}', date = date, content = content, outlinks = outlinks, outlinksss = outlinksss)

	def get_items(self):
		r, soup = self._initial_page()
		if '/s/' not in r.url:
			logger.warning('No public post list for this user')
			return
		while True:
			yield from self._soup_to_items(soup, r.url)
			pageLink = soup.find('a', attrs = {'class': 'tme_messages_more', 'data-before': True})
			if not pageLink:
				break
			nextPageUrl = urllib.parse.urljoin(r.url, pageLink['href'])
			r = self._get(nextPageUrl, headers = self._headers)
			if r.status_code != 200:
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
			soup = bs4.BeautifulSoup(r.text, 'lxml')

	def _get_entity(self):
		kwargs = {}
		# /channel has a more accurate member count and bigger profile picture
		r = self._get(f'https://t.me/{self._name}', headers = self._headers)
		if r.status_code != 200:
			raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
		soup = bs4.BeautifulSoup(r.text, 'lxml')
		membersDiv = soup.find('div', class_ = 'tgme_page_extra')
		if membersDiv.text.endswith(' members'):
			kwargs['members'] = int(membersDiv.text[:-8].replace(' ', ''))
		kwargs['photo'] = soup.find('img', class_ = 'tgme_page_photo_image').attrs['src']

		r, soup = self._initial_page()
		if '/s/' not in r.url: # Redirect on channels without public posts
			return
		channelInfoDiv = soup.find('div', class_ = 'tgme_channel_info')
		assert channelInfoDiv, 'channel info div not found'
		titleDiv = channelInfoDiv.find('div', class_ = 'tgme_channel_info_header_title')
		kwargs['title'] = titleDiv.find('span').text
		kwargs['verified'] = bool(titleDiv.find('i', class_ = 'verified-icon'))
		kwargs['username'] = channelInfoDiv.find('div', class_ = 'tgme_channel_info_header_username').text[1:] # Remove @
		descriptionDiv = channelInfoDiv.find('div', class_ = 'tgme_channel_info_description')
		if descriptionDiv:
			kwargs['description'] = descriptionDiv.text

		def parse_num(s):
			s = s.replace(' ', '')
			if s.endswith('M'):
				return int(float(s[:-1]) * 1e6), 10 ** (6 if '.' not in s else 6 - len(s[:-1].split('.')[1]))
			elif s.endswith('K'):
				return int(float(s[:-1]) * 1000), 10 ** (3 if '.' not in s else 3 - len(s[:-1].split('.')[1]))
			else:
				return int(s), 1

		for div in channelInfoDiv.find_all('div', class_ = 'tgme_channel_info_counter'):
			value, granularity = parse_num(div.find('span', class_ = 'counter_value').text)
			type_ = div.find('span', class_ = 'counter_type').text
			if type_ == 'members':
				# Already extracted more accurately from /channel, skip
				continue
			elif type_ in ('photos', 'videos', 'links', 'files'):
				kwargs[type_], kwargs[f'{type_}Granularity'] = value, granularity

		return Channel(**kwargs)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('channel', help = 'A channel name')

	@classmethod
	def from_args(cls, args):
		return cls(args.channel, retries = args.retries)
