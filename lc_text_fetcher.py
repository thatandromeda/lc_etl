import os
import re
from time import sleep
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests

# TODO do I want to fetch blogs? I've filtered them out of slurp, but a
# general-purpose thing might need to catch it.
# TODO add support for fetching from URL? Simple to delegate that to existing
# functionality.
# TODO inheritance uncomfortably deep


TIMEOUT = 2

class UnknownIdentifier(Exception):
    pass


class UnknownHandler(Exception):
    pass


class SearchResultToText(object):
    def __init__(self, image_url):
        self.image_url = image_url


    def _http(self):
        # Get around intermittent 500s or whatever.
        retry = requests.packages.urllib3.util.retry.Retry(
            status=3, status_forcelist=[429, 500, 503]
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        http = requests.Session()
        http.mount("https://", adapter)
        http.mount("http://", adapter)

        return http


    def segment_path(self, image_url):
        raise NotImplementedError


    def request_url(self, image_path):
        raise NotImplementedError


    def parse_text(self, response):
        raise NotImplementedError


    def extract_image_path(self):
        return self.segment_path(self.image_url)


    def get_text(self, image_path):
        sleep(0.3)  # avoid rate-limiting
        return self._http().get(self.request_url(image_path), timeout=TIMEOUT)


    def full_text(self):
        image_path = self.extract_image_path()
        response = self.get_text(image_path)
        return self.parse_text(response)


class LcwebSearchResultToText(SearchResultToText):
    """Extract fulltext of items whose images are hosted on lcweb2."""

    endpoint = 'https://lcweb2.loc.gov/'

    def parse_text(self, response):
        # Even though it's an xml document, we'll get better results if we use the
        # html parser; the xml parser will add "body" and "html" tags above the top
        # level of the xml document, and then get confused about the "body" tags
        # which will exist at different, nested levels of the document.
        soup = BeautifulSoup(response.text, 'html.parser')
        # Any child tags of 'p' will be rendered as None by tag.string, so we remove
        # them with the if condition. There are frequent subtags, like 'pageinfo'
        # (page metadata), which we do not want because they do not contain the
        # actual text.
        text = "\n".join([str(tag.string)
                          for tag in soup.body.find_all('p')
                          if tag.string])

        # Smart quotes, and UnicodeDammit doesn't know how to detwingle them.
        text = text.replace('â\x80\x9c', '"')
        text = text.replace('â\x80\x9d', '"')

        return text


    def segment_path(self, url):
        path = urlparse(url).path
        base_path = os.path.splitext(path)[0]   # Remove file extension.
        return f'{base_path}.xml'


    def request_url(self, image_path):
        return f'{self.endpoint}{self.segment_path(image_path)}'


class TileSearchResultToText(SearchResultToText):
    """Includes the features common to fetching fulltext whose images are stored
    on the tile.loc.gov server. Not intended to be used as-is."""

    def __init__(self, image_url):
        super(TileSearchResultToText, self).__init__(image_url)
        self.url_characters_no_period = r"-_~!*'();:@&=+$,?%#A-z0-9"
        self.url_characters = self.url_characters_no_period + '.'
        self.endpoint = 'https://tile.loc.gov/text-services/word-coordinates-service'


    def segment_path(self, image_url):
        image_path = urlparse(image_url).path
        try:
            return re.compile(self.lc_service_url).match(image_path).group('identifier')
        except AttributeError:
            raise UnknownIdentifier


    def request_url(self, image_path):
        return f'{self.endpoint}?full_text=1&format=alto_xml&segment=/{self.encoded_segment(image_path)}.xml'


    def parse_text(self, response):
        # Seems like practically a no-op, but allows for full_text to live in
        # the superclass by hooking into different text parsing methods in
        # subclasses.
        return response.text


class IiifSearchResultToText(TileSearchResultToText):
    """Extract fulltext of items whose images are hosted on tile (the IIIF
    server) under image services."""

    def __init__(self, image_url):
        super(IiifSearchResultToText, self).__init__(image_url)
        self.lc_service_prefix = r'image[\-_]services/iiif'
        self.lc_service_url = rf'/{self.lc_service_prefix}/'\
                              rf'(?P<identifier>[{self.url_characters}]+)/' \
                              rf'(?P<region>[{self.url_characters}]+)/' \
                              rf'(?P<size>[{self.url_characters}]+)/' \
                              rf'(?P<rotation>[{self.url_characters}]+)/' \
                              rf'(?P<quality>[{self.url_characters_no_period}]+)' \
                              rf'.(?P<format>[{self.url_characters}]+)'


    def encoded_segment(self, image_path):
        return image_path.replace(':', '/')


class StorageSearchResultToText(TileSearchResultToText):
    """Extract fulltext of items whose images are hosted on tile (the IIIF
    server) under storage services."""

    def __init__(self, image_url):
        super(StorageSearchResultToText, self).__init__(image_url)
        self.lc_service_prefix = r'storage[\-_]services'
        self.url_characters_with_slash = self.url_characters + '/'
        self.lc_service_url = rf'/{self.lc_service_prefix}/'\
                           rf'(?P<identifier>[{self.url_characters_with_slash}]+)/' \
                           rf'.(?P<format>[{self.url_characters_with_slash}]+)'


    def encoded_segment(self, image_path):
        return f"{image_path.replace(':', '/')}.alto"


    def alternate_url(self, image_path):
        return f'https://tile.loc.gov/storage-services/{image_path}.alto.xml'


    def get_text(self, image_path):
        first_attempt = super(StorageSearchResultToText, self).get_text(image_path)
        # Unfortunately we get a 200 even if the response fails, so we have to
        # check the contents of the response.
        if isinstance(first_attempt, list):
            return requests.get(self.alternate_url(image_path))
        else:
            return first_attempt


class Fetcher(object):
    def __init__(self, result):
        self.result = result
        self.server_to_handler = {
            'tile.loc.gov': self._tile_handler,
            'lcweb2.loc.gov': self._lcweb2_handler
        }


    def _tile_handler(self, image_url):
        if 'image-services' in image_url:
            return IiifSearchResultToText(image_url)
        elif 'storage-services' in image_url:
            return StorageSearchResultToText(image_url)
        else:
            raise UnknownHandler(f'No handler registered for {image_url}')


    def _lcweb2_handler(self, image_url):
        return LcwebSearchResultToText(image_url)


    def _single_url_full_text(self, image_url):
        server = urlparse(image_url).netloc
        return self.server_to_handler[server](image_url).full_text()


    def is_valid(self, text):
        return all([
            bool(text),
            not isinstance(text, list)
        ])


    def _get_text_from_image(self):
        text = None

        for image_url in self.result['image_url']:
            candidate = self._single_url_full_text(image_url)
            if self.is_valid(candidate):
                text = candidate
                break

        return text


    def _get_text_from_audio(self):
        return StorageSearchResultToText(image_url).full_text()


    def full_text(self):
        """
        Initialize a handler that knows how to fetch fulltext for images hosted
        on the given server, and delegate to its full_text method.

        Assumes that all image_urls correspond to the same text; therefore
        returns the first acceptable text.
        """

        if 'audio' in result['online_format']:
            return self._get_text_from_audio()
        else:
            return self._get_text_from_image()
