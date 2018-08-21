import datetime
import itertools
import json
import logging
import re
import snscrape.base


logger = logging.getLogger(__name__)


class GooglePlusUserScraper(snscrape.base.Scraper):
	name = 'googleplus-user'

	def __init__(self, user, **kwargs):
		super().__init__(**kwargs)
		self._user = user

	def get_items(self):
		headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

		logger.info('Retrieving initial data')
		r = self._get(f'https://plus.google.com/{self._user}', headers = headers)
		if r.status_code == 404:
			logger.warning('User does not exist')
			return
		elif r.status_code != 200:
			logger.error(f'Got status code {r.status_code}')
			return

		# Global data; only needed for the session ID
		#TODO: Make this more robust somehow
		match = re.search(r'''(['"])FdrFJe\1\s*:\s*(['"])(?P<sid>.*?)\2''', r.text)
		if not match:
			logger.error('Unable to find session ID')
			return
		sid = match.group('sid')

		# Page data
		# As of 2018-05-18, the much simpler regex r'''<script[^>]*>AF_initDataCallback\(\{key: 'ds:6',.*?return (.*?)\}\}\);</script>''' would work also, but this is more generic and less likely to break:
		match = re.search(r'''<script[^>]*>\s*(?:.*?)\s*\(\s*\{(?:|.*?,)\s*key\s*:\s*(['"])ds:6\1\s*,.*?,\s*data\s*:\s*function\s*\(\s*\)\s*\{\s*return\s*(?P<data>.*?)\}\s*\}\s*\)\s*;\s*</script>''', r.text, re.DOTALL)
		if not match:
			logger.error('Unable to extract data')
			return
		jsonData = match.group('data')
		response = json.loads(jsonData)
		if response[0][7] is None:
			logger.info('User has no posts')
			return
		for postObj in response[0][7]:
			yield snscrape.base.URLItem(f'https://plus.google.com/{postObj[6]["33558957"][21]}')
		cursor = response[0][1] # 'ADSJ_x'
		if cursor is None:
			# No further pages
			return
		baseDate = datetime.datetime.utcnow()
		baseSeconds = baseDate.hour * 3600 + baseDate.minute * 60 + baseDate.second
		userid = response[1] # Alternatively and more ugly: response[0][7][0][6]['33558957'][16]

		for counter in itertools.count(start = 2):
			logger.info('Retrieving next page')
			reqid = 1 + baseSeconds + int(1e5) * counter
			r = self._post(
			    f'https://plus.google.com/_/PlusAppUi/data?ds.extension=74333095&f.sid={sid}&hl=en-US&soc-app=199&soc-platform=1&soc-device=1&_reqid={reqid}&rt=c',
			    data = [('f.req', '[[[74333095,[{"74333095":["' + cursor + '","' + userid + '"]}],null,null,0]]]'), ('', '')],
			    headers = headers
			  )
			if r.status_code != 200:
				logger.error(f'Got status code {r.status_code}')
				return

			# As if everything up to here wasn't terrible already, this is where it gets *really* bad.
			# The API contains a few junk characters at the beginning, apparently as an anti-CSRF measure.
			# The remainder is effectively a self-made chunked transfer encoding but with decimal digits and including everything except the digits themselves in the chunk size.
			# It sucks.
			# Each chunk is actually one JSON object; you'd think that we can just read the first one and parse that, but there are some quirks that make this difficult.
			# I was unable to figure out what the "chunk size" actually covers exactly; the response is UTF-8 encoded, but the chunk size matches neither the binary nor the decoded length.
			# Enter the awful workaround: strip away the initial chunk size, then parse the beginning of the remaining data using a parser that doesn't care if there's junk after the JSON.

			garbage = r.text
			assert garbage[:6] == ")]}'\n\n" # anti-CSRF and two newlines
			data = []
			pos = 6
			while garbage[pos].isdigit() or garbage[pos].isspace(): # Also strip leading whitespace
				pos += 1
			response = json.JSONDecoder().raw_decode(''.join(garbage[pos:]))[0] # Parses only the first structure in the data stream without throwing an error about the extra data at the end

			for postObj in response[0][2]['74333095'][0][7]:
				yield snscrape.base.URLItem(f'https://plus.google.com/{postObj[6]["33558957"][21]}')

			cursor = response[0][2]['74333095'][0][1]

			if cursor is None:
				break

	@classmethod
	def setup_parser(cls, subparser):
		subparser.add_argument('user', help = 'A Google Plus username (with leading "+") or numeric ID')

	@classmethod
	def from_args(cls, args):
		return cls(args.user, retries = args.retries)
