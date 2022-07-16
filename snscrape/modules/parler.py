import collections
import dataclasses
import snscrape.base
import typing
import logging

_logger = logging.getLogger(__name__)

@dataclasses.dataclass
class Post(snscrape.base.Item):
    '''An object representing one post.

    Most fields can be None if not known.
    '''

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
    is_echo: bool #?
    link: list # represented as a str, though, so we'll have to parse that
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
    # FIXME: add video, video_data
    # video and video_data might be the same as image and image_data
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
            return False, "non-200 status code"
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
            raise ValueError(f"Bad username: {usernameIsInvalid}")

        super().__init__(**kwargs)
        self._username = username.strip()
        self._apiHeaders['user'] = self._username

    def _is_username_invalid(self, username):
        if not username:
            return "empty query"
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
            current_page = self._get_api_data("https://parler.com/open-api/ProfileFeedEndpoint.php", data)
            if previous_page == current_page:
                break
            previous_page = current_page
            page += 1
            yield current_page
