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
    V2LINKLONG: str
    audio_data: str
    url: str
    badges: 'Badges'
    body: str
    commentCount: int
    commented: bool
    dateCreated: str
    detectedLanguage: str
    domainName: str
    echoCount: int
    # FIXME: Add echoed, echoedWithCommentId, echoedWithoutCommentId
    edited: bool
    # FIXME: add embed_data
    fullBody: str
    hasAudio: bool
    hasEmbed: bool
    hasImage: bool
    hasVideo: bool
    id: int
    image: str
    image_data: str
    image_nsfw: bool
    is_echo: bool
    link: list[str]
    long_link: str
    name: str
    profilePhoto: str
    sensitive: bool
    time_ago: str
    title: str
    trolling: bool # don't even ask bc i don't know
    username: str
    userv4uuid: str
    uuid: str
    v4uuid: str
    video: bool
    video_data: str
    voteCount: int

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
class User(snscrape.base.Entity):
    '''A Parler user.'''

    status: str
    followerCount: int
    readableFollowerCount: str
    followingCount: 10
    readableFollowingCount: str
    coverPhoto: str
    profilePhoto: str
    badges: list[str]
    allBadges: list['Badge']
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

    def _is_username_invalid(self, username):
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
            This method is a generator. The number of tweets is not known beforehand.
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
            current_page['link'] = json.loads(current_page['link']) # why
            if previous_page == current_page:
                break
            previous_page = current_page
            page += 1
            yield current_page
