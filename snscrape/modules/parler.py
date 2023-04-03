__all__ = [
		'Parley', 'User', 'ParlerParleyScraper'
]

import dataclasses
import json
import snscrape.base
import snscrape.utils
import typing

@dataclasses.dataclass
class User(snscrape.base.Item):
	uuid: str
	name: str
	username: str
	badges: typing.Dict[str, bool]
	bio: str
	location: str
	website: str
	birthday: typing.Optional[str]
	realName: typing.Optional[str]
	joinedDate: str
	followingCount: int
	followerCount: int
	isPrivate: bool
	isPublic: bool
	isFollowed: bool
	isFollowedPending: bool
	isSubscribed: bool
	isMuted: bool
	isBlocked: bool
	profilePhoto: str
	coverPhoto: str

	gender: typing.Optional[str] = None

@dataclasses.dataclass
class Parley(snscrape.base.Item):
	postuuid: str
	body: str
	totalComments: int
	comments: int
	echos: int
	upvotes: int
	views: int
	isEcho: bool
	isComment: bool
	isUpvoted: bool
	isCommented: bool
	isReplied: bool
	isDiscovered: bool
	isSuggested: bool
	hasEcho: bool
	hasEchoComment: bool
	sensitive: bool
	trolling: bool
	image: str
	detectedLanguage: str
	state: int
	edited: bool
	videoProcessingStatus: str
	dateCreated: str
	dateUpdated: str
	isEchoComment: bool
	processed: bool
	user: User

	title: typing.Optional[str] = None # this appears to be in OpenGraph embeds
	link: typing.Optional[str] = None
	imageId: typing.Optional[str] = None
	video: typing.Optional[str] = None
	images: typing.Optional[typing.List[str]] = None
	audioData: typing.Optional[str] = None
	embedData: typing.Optional[str] = None
	parent: typing.Optional['Parley'] = None

	def __str__(self):
		return f'https://parler.com/feed/{self.postuuid}'

class _ParlerAPIScraper(snscrape.base.Scraper):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._apiHeaders = {
				'Accept-Language': 'en-US,en;q=0.9',
				'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.420 Safari/537.69',
		}

	def _check_api_response(self, r):
		if r.status_code != 200:
			return False, 'non-200 status code'
		try:
			if r.json().get("status") != "success":
				return False, 'Bad API response: invalid or missing status'
			return True, None
		except json.JSONDecodeError as e:
			return False, 'Bad API response: unparseable JSON'

	def _get_api_data(self, path):
		r = self._get(path, headers = self._apiHeaders, responseOkCallback = self._check_api_response)
		# At this point, we've already validated the JSON through the check_api_response callback, so a failure here should raise an exception
		return r.json()

class ParlerParleyScraper(_ParlerAPIScraper):
	name = 'parler-parley'

	def __init__(self, identifier, **kwargs):
		super().__init__(**kwargs)
		# TODO: We really should validate the UUID before we attempt to contact the API. Just a regex check should be fine.
		self.identifier = identifier

	def get_items(self) -> typing.Iterator[Parley]:
		endpoint = f'https://api.parler.com/v0/public/parleys/{self.identifier}'
		data = self._get_api_data(endpoint)['data']
		del data['user']['is_following'] # I believe this is only ever True if logged in
		del data['comment_path'] # Comments aren't accessible when not logged in
		del data['ad'] # seems useless
		data['user'] = User(**snscrape.utils.snake_to_camel(**data['user']))
		yield Parley(**snscrape.utils.snake_to_camel(**data))

	@classmethod
	def _cli_setup_parser(cls, subparser):
		def parley(s):
			return s

		subparser.add_argument('parley', type = parley, help = 'UUID of a Parley')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, identifier = args.parley)
