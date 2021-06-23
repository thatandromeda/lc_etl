import os
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests

# TODO do I want to fetch blogs? I've filtered them out of slurp, but a
# general-purpose thing might need to catch it.
# TODO add support for fetching from URL? Simple to delegate that to existing
# functionality.


class UnknownIdentifier(Exception):
    pass


class SearchResultToText(object):
    def __init__(self, result):
        self.result = result


    def segment_path(self, image_url):
        raise NotImplementedError


    def request_url(self, image_path):
        raise NotImplementedError


    def parse_text(self, response):
        raise NotImplementedError


    def extract_image_paths(self):
        image_urls = self.result['image_url']    # laughable absence of error-handling
        image_paths = [self.segment_path(image_url) for image_url in image_urls]
        return list(set(image_paths))    # deduplicate. is this ever needed??


    def full_text(self):
        image_paths = self.extract_image_paths()
        texts = []

        for image_path in image_paths:
            response = requests.get(self.request_url(image_path)) # laughable absence of error-handling

            texts.append(self.parse_text(response))

        return texts


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


    def full_text(self):
        image_paths = self.extract_image_paths()
        texts = []

        for image_path in image_paths:
            response = requests.get(self.request_url(image_path))
            texts.append(self.parse_text(response))

        return texts


class IiifSearchResultToText(SearchResultToText):
    """Extract fulltext of items whose images are hosted on tile (the IIIF
    server) under image services."""

    def __init__(self, result):
        super(IiifSearchResultToText, self).__init__(result)
        self.lc_service_prefix = r'image[\-_]services/iiif'
        self.url_characters_no_period = r"-_~!*'();:@&=+$,?%#A-z0-9"
        self.url_characters = self.url_characters_no_period + '.'
        self.lc_service_url = rf'/{self.lc_service_prefix}/'\
                              rf'(?P<identifier>[{self.url_characters}]+)/' \
                              rf'(?P<region>[{self.url_characters}]+)/' \
                              rf'(?P<size>[{self.url_characters}]+)/' \
                              rf'(?P<rotation>[{self.url_characters}]+)/' \
                              rf'(?P<quality>[{self.url_characters_no_period}]+)' \
                              rf'.(?P<format>[{self.url_characters}]+)'

        self.endpoint = 'https://tile.loc.gov/text-services/word-coordinates-service'


    def segment_path(self, image_url):
        image_path = urlparse(image_url).path
        try:
            return re.compile(self.lc_service_url).match(image_path).group('identifier')
        except AttributeError:
            raise UnknownIdentifier


    def encoded_segment(self, image_path):
        return image_path.replace(':', '/')


    def request_url(self, image_path):
        return f'{self.endpoint}?full_text=1&format=alto_xml&segment=/{self.encoded_segment(image_path)}.xml'


    def parse_text(self, response):
        # Seems like practically a no-op, but allows for full_text to live in
        # the superclass by hooking into different text parsing methods in
        # subclasses.
        return response.text


class StorageSearchResultToText(IiifSearchResultToText):
    """Extract fulltext of items whose images are hosted on tile (the IIIF
    server) under storage services."""

    def __init__(self, result):
        super(StorageSearchResultToText, self).__init__(result)
        self.lc_service_prefix = r'storage[\-_]services'
        self.url_characters_with_slash = self.url_characters + '/'
        self.lc_service_url = rf'/{self.lc_service_prefix}/'\
                           rf'(?P<identifier>[{self.url_characters_with_slash}]+)/' \
                           rf'.(?P<format>[{self.url_characters_with_slash}]+)'


    def encoded_segment(self, image_path):
        return f"{image_path.replace(':', '/')}.alto"


class Fetcher(object):
    server_to_handler = {
        'tile.loc.gov': IiifSearchResultToText,
        'lcweb2.loc.gov': LcwebSearchResultToText
    }

    def full_text(self, result):
        """
        Initialize a handler that knows how to fetch fulltext for images hosted
        on the given server, and delegate to its full_text method.
        """
        server = urlparse(result['image_url'][0]).netloc
        return self.server_to_handler[server](result).full_text()
