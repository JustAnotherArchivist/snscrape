import dataclasses
import datetime
import logging
import re
import snscrape.base
import snscrape.version
import string
import time
import typing


logger = logging.getLogger(__name__)


# Most of these fields should never be None, but due to broken data, they sometimes are anyway...

@dataclasses.dataclass
class Submission(snscrape.base.Item):
	author: typing.Optional[str] # E.g. submission hf7k6
	created: datetime.datetime
	id: str
	link: typing.Optional[str]
	selftext: typing.Optional[str]
	subreddit: typing.Optional[str] # E.g. submission 617p51
	title: str
	url: str

	def __str__(self):
		return self.url


@dataclasses.dataclass
class Comment(snscrape.base.Item):
	author: typing.Optional[str]
	body: str
	created: datetime.datetime
	id: str
	parentId: typing.Optional[str]
	subreddit: typing.Optional[str]
	url: str

	def __str__(self):
		return self.url


class RedditPushshiftScraper(snscrape.base.Scraper):
	def __init__(self, submissions = True, comments = True, before = None, after = None, **kwargs):
		super().__init__(**kwargs)
		self._submissions = submissions
		self._comments = comments
		self._before = before
		self._after = after

		if not self._submissions and not self._comments:
			raise ValueError('At least one of submissions and comments must be True')

	def _handle_rate_limiting(self, r):
		if r.status_code == 429:
			logger.info('Got 429 response, sleeping')
			time.sleep(10)
			return False, 'rate-limited'
		if r.status_code != 200:
			return False, 'non-200 status code'
		return True, None

	def _cmp_id(self, id1, id2):
		'''Compare two Reddit IDs. Returns -1 if id1 is less than id2, 0 if they are equal, and 1 if id1 is greater than id2.

		id1 and id2 may have prefixes like t1_, but if included, they must be present on both and equal.'''

		if id1.startswith('t') and '_' in id1:
			prefix, id1 = id1.split('_', 1)
			if not id2.startswith(f'{prefix}_'):
				raise ValueError('id2 must have the same prefix as id1')
			_, id2 = id2.split('_', 1)
		if id1.strip(string.ascii_lowercase + string.digits) != '':
			raise ValueError('invalid characters in id1')
		if id2.strip(string.ascii_lowercase + string.digits) != '':
			raise ValueError('invalid characters in id2')
		if len(id1) < len(id2):
			return -1
		if len(id1) > len(id2):
			return 1
		if id1 < id2:
			return -1
		if id1 > id2:
			return 1
		return 0

	def _iter_api(self, url, params = None):
		'''Iterate through the Pushshift API using the 'before' parameter and yield the items.'''
		lowestIdSeen = None
		if params is None:
			params = {}
		if self._before is not None:
			params['before'] = self._before
		if self._after is not None:
			params['after'] = self._after
		params['sort'] = 'desc'
		while True:
			r = self._get(url, params = params, headers = {'User-Agent': f'snscrape/{snscrape.version.__version__}'}, responseOkCallback = self._handle_rate_limiting)
			if r.status_code != 200:
				raise snscrape.base.ScraperException(f'Got status code {r.status_code}')
			obj = r.json()
			if not obj['data'] or (lowestIdSeen is not None and all(self._cmp_id(d['id'], lowestIdSeen) >= 0 for d in obj['data'])): # end of pagination
				break
			for d in obj['data']:
				if lowestIdSeen is None or self._cmp_id(d['id'], lowestIdSeen) == -1:
					yield self._api_obj_to_item(d)
					lowestIdSeen = d['id']
			params['before'] = obj["data"][-1]["created_utc"] + 1

	def _api_obj_to_item(self, d):
		cls = Submission if 'title' in d else Comment

		# Pushshift doesn't always return a permalink; sometimes, there's a permalink_url instead, and sometimes there's nothing at all
		permalink = d.get('permalink')
		if permalink is None:
			# E.g. comment dovj2v7
			permalink = d.get('permalink_url')
			if permalink is None:
				if 'link_id' in d and d['link_id'].startswith('t3_'): # E.g. comment doraazf
					if 'subreddit' in d:
						permalink = f'/r/{d["subreddit"]}/comments/{d["link_id"][3:]}/_/{d["id"]}/'
					else: # E.g. submission 617p51 but can likely happen for comments as well
						permalink = f'/comments/{d["link_id"][3:]}/_/{d["id"]}/'
				else:
					logger.warning(f'Unable to find or construct permalink')
					permalink = '/'

		kwargs = {
			'author': d.get('author'),
			'created': datetime.datetime.fromtimestamp(d['created_utc'], datetime.timezone.utc),
			'url': f'https://old.reddit.com{permalink}',
			'subreddit': d.get('subreddit'),
		}
		if cls is Submission:
			kwargs['selftext'] = d.get('selftext') or None
			kwargs['link'] = (d['url'] if not d['url'].startswith('/') else f'https://old.reddit.com{d["url"]}') if not kwargs['selftext'] else None
			if kwargs['link'] == kwargs['url'] or kwargs['url'].replace('//old.reddit.com/', '//www.reddit.com/') == kwargs['link']:
				kwargs['link'] = None
			kwargs['title'] = d['title']
			kwargs['id'] = f't3_{d["id"]}'
		else:
			kwargs['body'] = d['body']
			kwargs['parentId'] = d.get('parent_id')
			kwargs['id'] = f't1_{d["id"]}'

		return cls(**kwargs)

	def _iter_api_submissions_and_comments(self, params: dict):
		# Retrieve both submissions and comments, interleave the results to get a reverse-chronological order
		params['size'] = '1000'
		if self._submissions:
			submissionsIter = self._iter_api('https://api.pushshift.io/reddit/search/submission/', params.copy()) # Pass copies to prevent the two iterators from messing each other up by using the same dict
		else:
			submissionsIter = iter(())
		if self._comments:
			commentsIter = self._iter_api('https://api.pushshift.io/reddit/search/comment/', params.copy())
		else:
			commentsIter = iter(())

		try:
			tipSubmission = next(submissionsIter)
		except StopIteration:
			# There are no submissions, just yield comments and return
			yield from commentsIter
			return
		try:
			tipComment = next(commentsIter)
		except StopIteration:
			# There are no comments, just yield submissions and return
			yield tipSubmission
			yield from submissionsIter
			return

		while True:
			# Return newer first; if both have the same creation datetime, return the comment first
			if tipSubmission.created > tipComment.created:
				yield tipSubmission
				try:
					tipSubmission = next(submissionsIter)
				except StopIteration:
					# Reached the end of submissions, just yield the remaining comments and stop
					yield tipComment
					yield from commentsIter
					break
			else:
				yield tipComment
				try:
					tipComment = next(commentsIter)
				except StopIteration:
					yield tipSubmission
					yield from submissionsIter
					break

	@classmethod
	def _setup_parser_opts(cls, subparser):
		subparser.add_argument('--no-submissions', dest = 'noSubmissions', action = 'store_true', default = False, help = 'Don\'t list submissions')
		subparser.add_argument('--no-comments', dest = 'noComments', action = 'store_true', default = False, help = 'Don\'t list comments')
		subparser.add_argument('--before', metavar = 'TIMESTAMP', type = int, help = 'Fetch results before a Unix timestamp')
		subparser.add_argument('--after', metavar = 'TIMESTAMP', type = int, help = 'Fetch results after a Unix timestamp')


def _make_scraper(name_, validationFunc, apiField):
	class Scraper(RedditPushshiftScraper):
		name = f'reddit-{name_}'

		def __init__(self, name, **kwargs):
			super().__init__(**kwargs)
			self._name = name
			if not validationFunc(self._name):
				raise ValueError(f'invalid {name_} name')

		def get_items(self):
			yield from self._iter_api_submissions_and_comments({apiField: self._name})

		@classmethod
		def setup_parser(cls, subparser):
			super()._setup_parser_opts(subparser)
			subparser.add_argument(name_, type = snscrape.base.nonempty_string(name_))

		@classmethod
		def from_args(cls, args):
			return cls._construct(args, getattr(args, name_), submissions = not args.noSubmissions, comments = not args.noComments, before = args.before, after = args.after)

	Scraper.__name__ = f'Reddit{name_.capitalize()}Scraper'
	Scraper.__qualname__ = Scraper.__name__
	globals()[Scraper.__name__] = Scraper


_make_scraper('user', lambda x: re.match('^[A-Za-z0-9_-]{3,20}$', x), 'author')
_make_scraper('subreddit', lambda x: re.match('^[A-Za-z0-9][A-Za-z0-9_]{2,20}$', x), 'subreddit')
_make_scraper('search', lambda x: True, 'q')
