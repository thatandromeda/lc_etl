import re
from urllib.parse import urlparse

import requests

LC_IIIF_PREFIX = r'image[\-_]services/iiif'
URL_CHARACTERS_NO_PERIOD = r"-_~!*'();:@&=+$,?%#A-z0-9"
URL_CHARACTERS = URL_CHARACTERS_NO_PERIOD + '.'
IIIF_URL = rf'/{LC_IIIF_PREFIX}/'\
           rf'(?P<identifier>[{URL_CHARACTERS}]+)/' \
           rf'(?P<region>[{URL_CHARACTERS}]+)/' \
           rf'(?P<size>[{URL_CHARACTERS}]+)/' \
           rf'(?P<rotation>[{URL_CHARACTERS}]+)/' \
           rf'(?P<quality>[{URL_CHARACTERS_NO_PERIOD}]+)' \
           rf'.(?P<format>[{URL_CHARACTERS}]+)'
LC_IIIF_URL_FORMAT = re.compile(IIIF_URL)

ENDPOINT = 'https://tile.loc.gov/text-services/word-coordinates-service'


def segment_id(image_url):
    image_path = urlparse(image_url).path
    return LC_IIIF_URL_FORMAT.match(image_path).group('identifier')


def encoded_segment(image_path):
    return image_path.replace(':', '/')


def full_text(result):
    image_urls = result['image_url']    # laughable absence of error-handling
    image_paths = [segment_id(image_url) for image_url in image_urls]
    image_paths = list(set(image_paths))    # deduplicate. is this ever needed??

    payload_str = 'full_text=1'
    for image_path in image_paths:
        payload_str += f'&format=alto_xml&segment=/{encoded_segment(image_path)}.xml'

    response = requests.get(ENDPOINT, params=payload_str) # laughable absence of error-handling

    return response.text
