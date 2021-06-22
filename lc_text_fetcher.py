import os
import re
from urllib.parse import urlparse

import bs4 as BeautifulSoup
import requests

# TODO throw a custom exception in segment_path and catch it in slurp


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

    ENDPOINT = 'https://lcweb2.loc.gov/'

    def parse_text(self, response):
        # Even though it's an xml document, we'll get better results if we use the
        # html parser; the xml parser will add "body" and "html" tags above the top
        # level of the xml document, and then get confused about the "body" tags
        # which will exist at different, nested levels of the document.
        soup = BeautifulSoup(response.text,  'html.parser')
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
        return f'{ENDPOINT}{self.segment_path(image_path)}'


    def full_text(self):
        image_paths = self.extract_image_paths()
        texts = []

        for image_path in image_paths:
            response = requests.get(self.request_url(image_path))
            texts.append(self.parse_text(response))

        return texts


class IiifSearchResultToText(SearchResultToText):
    """Extract fulltext of items whose images are hosted on tile (the IIIF
    server)."""

    lc_iiif_prefix = r'image[\-_]services/iiif'
    url_characters_no_period = r"-_~!*'();:@&=+$,?%#A-z0-9"
    url_characters = url_characters_no_period + '.'
    iiif_url = rf'/{lc_iiif_prefix}/'\
               rf'(?P<identifier>[{url_characters}]+)/' \
               rf'(?P<region>[{url_characters}]+)/' \
               rf'(?P<size>[{url_characters}]+)/' \
               rf'(?P<rotation>[{url_characters}]+)/' \
               rf'(?P<quality>[{url_characters_no_period}]+)' \
               rf'.(?P<format>[{url_characters}]+)'
    lc_iiif_url_format = re.compile(iiif_url)

    endpoint = 'https://tile.loc.gov/text-services/word-coordinates-service'


    def segment_path(self, image_url):
        image_path = urlparse(image_url).path
        try:
            return self.lc_iiif_url_format.match(image_path).group('identifier')
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
