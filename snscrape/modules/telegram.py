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


class TelegramChannelScraper(snscrape.base.Scraper):
	name = 'telegram-channel'

	def __init__(self, name, **kwargs):
		super().__init__(**kwargs)
		self._name = name

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
		headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'}

		nextPageUrl = f'https://t.me/s/{self._name}'
		while True:
			r = self._get(nextPageUrl, headers = headers)
			if r.status_code != 200:
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
			soup = bs4.BeautifulSoup(r.text, 'lxml')
			yield from self._soup_to_items(soup, nextPageUrl)
			pageLink = soup.find('a', attrs = {'class': 'tme_messages_more', 'data-before': True})
			if not pageLink:
				break
			nextPageUrl = urllib.parse.urljoin(nextPageUrl, pageLink['href'])

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('channel', help = 'A channel name')

	@classmethod
	def from_args(cls, args):
		return cls(args.channel, retries = args.retries)
