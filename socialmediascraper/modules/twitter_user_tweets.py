import bs4
import json
import logging
import socialmediascraper.base


logger = logging.getLogger(__name__)


class TwitterUserTweetsScraper(socialmediascraper.base.Scraper):
	name = 'twitter-user-tweets'

	def __init__(self, username, **kwargs):
		super().__init__(**kwargs)
		self._username = username

	def _get_feed_from_html(self, html):
		soup = bs4.BeautifulSoup(html, 'lxml')
		feed = soup.find_all('li', 'js-stream-item')
		return feed

	def _feed_to_items(self, feed):
		for tweet in feed:
			username = tweet.find('span', 'username').find('b').text
			tweetID = tweet['data-item-id']
			yield socialmediascraper.base.URLItem(f'https://twitter.com/{username}/status/{tweetID}')

	def _check_json_callback(self, r):
		if r.headers['content-type'] != 'application/json;charset=utf-8':
			logger.error(f'Content type of {r.url} is not JSON')
			return False
		return True

	def get_items(self):
		query = f'from:{self._username}'
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

		# First page
		logger.info(f'Retrieving search page for {query}')
		r = self._get('https://twitter.com/search', params = {'f': 'tweets', 'vertical': 'default', 'lang': 'en', 'q': query, 'src': 'typd'}, headers = headers)

		feed = self._get_feed_from_html(r.text)
		if not feed:
			return
		newestID = feed[0]['data-item-id']
		maxPosition = f'TWEET-{feed[-1]["data-item-id"]}-{newestID}'
		yield from self._feed_to_items(feed)

		while True:
			logger.info(f'Retrieving scroll page {maxPosition}')
			r = self._get('https://twitter.com/i/search/timeline',
				params = {
					'f': 'tweets',
					'vertical': 'default',
					'lang': 'en',
					'q': query,
					'include_available_features': '1',
					'include_entities': '1',
					'reset_error_state': 'false',
					'src': 'typd',
					'max_position': maxPosition,
				},
				headers = headers,
				responseOkCallback = self._check_json_callback)

			feed = self._get_feed_from_html(json.loads(r.text)['items_html'])
			if not feed:
				return
			maxPosition = f'TWEET-{feed[-1]["data-item-id"]}-{newestID}'
			yield from self._feed_to_items(feed)

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('username', help = 'A Twitter username (without @)')

	@classmethod
	def from_args(cls, args):
		return cls(args.username, retries = args.retries)
