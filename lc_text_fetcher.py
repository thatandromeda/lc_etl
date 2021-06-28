import os
import re
from time import sleep
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup
import requests

# TODO do I want to fetch blogs? I've filtered them out of slurp, but a
# general-purpose thing might need to catch it.
# TODO inheritance uncomfortably deep
# TODO deal with responses like {url: {'full_text': 'blah'}}
# TODO audio still not working; see e.g. http://www.loc.gov/item/afc1941016_afs05499a/

TIMEOUT = 2

class UnknownIdentifier(Exception):
    pass


class UnknownHandler(Exception):
    pass


class ObjectNotOnline(Exception):
    pass


class SearchResultToText(object):
    def __init__(self, image_url):
        self.image_url = image_url
        self.url_characters_no_period = r"-_~!*'();:@&=+$,?%#A-z0-9"
        self.url_characters = self.url_characters_no_period + '.'
        self.url_characters_with_slash = self.url_characters + '/'
        self.not_found = rf'The requested URL {self.url_characters_with_slash}.xml was not found on this server.'


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


    def is_valid(self, response):
        return all([
            bool(response.text),
            not isinstance(response.text, list),
            not '"error":"[Errno 2] No such file or directory:' in response.text,
            not re.compile(self.not_found).match(response.text),
            response.status_code == 200
        ])


    def get_text(self, image_path):
        sleep(0.3)  # avoid rate-limiting
        return self._http().get(self.request_url(image_path), timeout=TIMEOUT)


    def full_text(self):
        image_path = self.extract_image_path()
        response = self.get_text(image_path)
        if self.is_valid(response):
            return self.parse_text(response)
        else:
            return None


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
        # Seems like almost a no-op, but allows for full_text to live in
        # the superclass by hooking into different text parsing methods in
        # subclasses.
        # The and condition means this will return None if the response is
        # empty.
        return response and response.text


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
        self.lc_service_url = rf'/{self.lc_service_prefix}/'\
                           rf'(?P<identifier>[{self.url_characters_with_slash}]+)/' \
                           rf'.(?P<format>[{self.url_characters_with_slash}]+)'


    def encoded_segment(self, image_path):
        return f"{image_path.replace(':', '/')}.alto"


    def alternate_urls(self, image_path):
        final_id = image_path.split('/')[-1]
        return [
            f'https://tile.loc.gov/storage-services/{image_path}.alto.xml',
            f'https://tile.loc.gov/storage-services/{image_path}/{final_id}.xml',
        ]


    def get_text(self, image_path):
        urls = [self.request_url(image_path)] + self.alternate_urls(image_path)

        for url in urls:
            response = self._http().get(url, timeout=TIMEOUT)
            if response:
                return response
            else:
                sleep(0.3)  # avoid rate-limiting

        return None


class Fetcher(object):
    """
    Fetch full text for Library of Congress items. Return None if full text is
    not found.

    Fetcher.full_text_from_url:
        Given the URL of an item, find its full text.

    Fetcher(result).full_text():
        Given the JSON representation of a single item, find its full text.

    OCRed text is stored on different servers with different URL formats, and
    the full text URL is not usually part of the search result, so there is no
    one single pattern for finding the OCR URL. Fetcher is actually responsible
    for identifying which of several handlers is most likely to succeed for this
    item, and delegating to its full_text() method.

    There are no guarantees about OCR quality; some texts may be unsuitable for
    some purposes. The caller is responsible for assessing quality.

    While Fetcher makes a good-faith attempt to respect rate limiting,
    intermittent server failures mean that text will not always be fetched even
    if it exists.
    """
    @classmethod
    def full_text_from_url(cls, url):
        """Given a URL of an item at LOC, fetches the fulltext of that item."""
        parsed_url = urlparse(url)
        base_url = urlunparse(
            (parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', 'fo=json', '')
        )
        result = requests.get(base_url).json()['item']
        return Fetcher(result).full_text()

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


    def _get_text_from_image(self):
        for image_url in self.result['image_url']:
            candidate = self._single_url_full_text(image_url)
            if candidate:
                return candidate

        return None


    def _get_text_from_audio(self):
        text = StorageSearchResultToText(image_url).full_text()
        return text


    def full_text(self):
        """
        Initialize a handler that knows how to fetch fulltext for images hosted
        on the given server, and delegate to its full_text method.

        Assumes that all image_urls correspond to the same text; therefore
        returns the first acceptable text.
        """

        try:
            format = self.result['online_format']
        except KeyError:
            raise ObjectNotOnline(f'{self.result['id']} does not have an online_format key')

        if 'audio' in format:
            return self._get_text_from_audio()
        else:
            return self._get_text_from_image()
