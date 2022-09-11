__all__ = [
		'Post', 'EngagementData', 'UserContext', 'Badges', 'Badge',
		'Video', 'User', 'ParlerProfileScraper'
]

import collections
import dataclasses
import json
import logging
import snscrape.base
import typing

_logger = logging.getLogger(__name__)

@dataclasses.dataclass
class Post(snscrape.base.Item):
	'''An object representing one post.

	Most fields can be None if not known.
	'''

	ad: bool
	V2LINKLONG: typing.List[str]
	audio_data: typing.Optional[str]
	badges: 'Badges'
	body: str
	date_created: str
	date_str: str
	detected_language: str
	depth: int
	domain_name: str
	edited: bool
	engagement: 'EngagementData'
	embed_data: typing.Optional[typing.Dict[str, str]] # Too few examples to try to parse this
	full_body: str
	has_audio: bool
	has_embed: bool
	has_image: bool
	has_video: bool
	id: int
	image: str
	image_data: str
	image_nsfw: bool
	is_echo: typing.Optional[bool]
	link: typing.List[str]
	long_link: str
	name: str
	root_post_uuid: typing.Optional[str] # Inferring
	parent_context_uuid: typing.Optional[str]
	profile_photo: str
	sensitive: bool
	time_ago: str
	time_str: str
	title: str
	trolling: bool # don't even ask bc i don't know
	username: str
	userv4uuid: str
	user_context: 'UserContext'
	uuid: str
	v4uuid: str
	video_data: typing.Optional['Video']
	view_count: int

	def __str__(self):
		return f"https://parler.com/feed/{self.uuid}"

@dataclasses.dataclass
class EngagementData:
	target: str
	target_id: int
	target_uuid: str
	echo_simple: bool
	echo_discuss: bool
	comment_count: int
	echo_count: int
	vote_count: int

@dataclasses.dataclass
class UserContext:
	owned_by_current_user: bool
	echo_of_current_user: bool
	reply_to_current_user: bool
	suggested: bool
	self_reported: bool

@dataclasses.dataclass
class Badges(snscrape.base.Item):
	gold: bool
	rss: bool
	private: bool
	early: bool
	parler_official: bool
	verified: bool
	parler_emp: bool

@dataclasses.dataclass
class Badge:
	'''Meant for use in allBadges'''

	name: str
	icon: str
	title: str
	description: str

@dataclasses.dataclass
class Video:
	'''A Parler video.'''

	contentType: str
	definition: int
	filenameExtension: str
	rootPath: str
	videoSrc: str
	thumbnailUrl: str
	videoId: str

@dataclasses.dataclass
class User(snscrape.base.Entity):
	'''A Parler user.'''

	status: str
	followerCount: int
	readableFollowerCount: str
	followingCount: 10
	readableFollowingCount: str
	coverPhoto: str
	profilePhoto: str
	badges: typing.List[str]
	allBadges: typing.List['Badge']
	isPrivateAccount: bool
	isPublicAccount: bool
	isPrivate: bool
	username: str
	dateCreated: str
	name: str
	uuid: str
	bio: str
	website: str
	location: str
	joinedAt: str
	showCommentTab: bool

	def __str__(self):
		return f'https://parler.com/{self.username}'

class _ParlerAPIScraper(snscrape.base.Scraper):
	'''Base class for all other Parler scraper classes.'''

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._apiHeaders = {
				'Accept-Language': 'en-US,en;q=0.9',
				'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.420 Safari/537.69',
		}

	def _check_api_response(self, r):
		if r.status_code != 200:
			return False, 'non-200 status code'
		return True, None

	def _get_api_data(self, endpoint, data):
		r = self._post(endpoint, data = data, headers = self._apiHeaders, responseOkCallback = self._check_api_response)
		try:
			obj = r.json()
		except json.JSONDecodeError as e:
			raise snscrape.base.ScraperException('Received invalid JSON from Parler') from e
		return obj

class ParlerProfileScraper(_ParlerAPIScraper):
	'''Scraper class, designed to scrape a Parler user.'''

	name = 'parler-user'

	def __init__(self, username, **kwargs):
		'''Args:
			username: Username of user to scrape. This is NOT their display name.

		Raises:
			ValueError: When username is invalid.
		'''

		usernameIsInvalid = self._is_username_invalid(username)
		if usernameIsInvalid:
			raise ValueError(f'Bad username: {usernameIsInvalid}')

		super().__init__(**kwargs)
		self._username = username.strip()
		self._apiHeaders['user'] = self._username

	def _get_entity(self):
		'''Get the entity behind the scraper, if any.

		This is the method implemented by subclasses for doing the actual retrieval/entity object creation. For accessing the scraper's entity, use the entity property.
		'''
		data = self._get_api_data('https://parler.com/api/profile_view.php', {'user': self._username})['data']
		data['allBadges'] = [Badge(**badge) for badge in data['allBadges']]
		dataclass_friendly_data = {key: value for key, value in data.items() if key in User.__annotations__}
		return User(**dataclass_friendly_data)

	@staticmethod
	def _is_username_invalid(username):
		if not username:
			return 'empty query'
		return False
		# FIXME: add more checks for invalid username

	def get_items(self) -> typing.Iterator[Post]:
		'''Get posts according to the specifications given when instantiating this scraper.

		Raises:
			ValueError, if the username is invalid
		Yields:
			Individual post.
		Returns:
			An iterator of posts.

		Note:
			This method is a generator. The number of posts is not known beforehand.
			Please keep in mind that the scraping results can potentially be a lot of posts.
		'''

		previous_page = 0
		current_page = 1
		page = 1
		data = {}
		data['user'] = (self._username)
		while True:
			data['page'] = (page)
			if data['page'] == 1:
				del data['page']
			current_page = self._get_api_data('https://parler.com/open-api/ProfileFeedEndpoint.php', data)
			for post in current_page['data']:
				primary = post['primary']
				post['user_context'] = {key: value for key, value in post['user_context'].items() if key in UserContext.__annotations__}
				primary['user_context'] = UserContext(**post['user_context'])
				primary['link'] = json.loads(primary['link']) if primary['link'] else [] # why
				primary['V2LINKLONG'] = json.loads(primary['V2LINKLONG']) if primary['link'] else []
				primary['ad'] = post['ad']
				engagement = post['engagement']
				engagement['comment_count'] = engagement['commentCount']
				engagement['vote_count'] = engagement['voteCount']
				engagement['echo_count'] = engagement['echoCount']
				engagement = {key: value for key, value in engagement.items() if key in EngagementData.__annotations__}
				primary['engagement'] = EngagementData(**engagement)
				primary['video'] = Video(**primary['video']) if primary['video'] else None
				primary = {key: value for key, value in primary.items() if key in Post.__annotations__}
				yield Post(**primary)
			if previous_page == current_page:
				break
			previous_page = current_page
			page += 1

	@classmethod
	def _cli_setup_parser(cls, subparser):
		def user(s):
			if cls._is_username_invalid(s):
				raise ValueError('Invalid username')
			return s

		subparser.add_argument('user', type = user, help = 'A Parler username (without @)')

	@classmethod
	def _cli_from_args(cls, args):
		return cls._cli_construct(args, username = args.user)
