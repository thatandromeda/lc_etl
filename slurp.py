from collections import defaultdict
import logging
import time
from urllib.parse import urlparse

import requests

from locr import Fetcher, UnknownIdentifier

timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())

PAGE_LENGTH = 1000  # LOC API team thinks this is the maximum allowable
TIMEOUT = 3

def http_adapter():
    # Get around intermittent 500s or whatever.
    retry = requests.packages.urllib3.util.retry.Retry(
        status=3, status_forcelist=[429, 500, 503]
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    return http


class LocUrl(object):
    """docstring for LocUrl."""

    def __init__(self, **kwargs):
        super(LocUrl, self).__init__()
        self.collection = kwargs.get('collection')
        self.query = kwargs.get('q')
        self.subject = kwargs.get('subject')
        self.identifier = kwargs.get('identifier')
        self.format = kwargs.get('format')
        self.title = kwargs.get('title')
        self.validate()
        self.base = 'https://www.loc.gov'
        self.kwargs = ['fo=json']

    def validate(self):
        endpoints = [self.identifier, self.collection, self.format, self.query]
        if len(list(filter(lambda x: x is not None, endpoints))) == 0:
            raise('Must specify an endpoint (identifier, collection, format) or query')
        elif len(list(filter(lambda x: x is not None, endpoints))) > 1:
            raise('May specify only endpoint (identifier, collection, format, or query)')

        if self.identifier and self.subject:
            raise('Cannot specify both an item identifier and a subject')


    def slugify(self, value):
        return value.replace(' ', '-')


    def construct(self):
        if self.collection:
            endpoint = f'{self.base}/collection/{self.slugify(self.collection)}'
        elif self.identifier:
            endpoint = f'{self.base}/item/{self.collection}'
        else:
            endpoint = f'{self.base}/search'

        if self.subject:
            self.kwargs.append(f'fa=subject:{self.subject}')

        if self.query:
            self.kwargs.append(f'q={self.slugify(self.query)}')

        if self.title:
            self.kwargs.append(f'fa=partof_title:{self.slugify(self.title)}')

        querystring = '&'.join(self.kwargs)

        return f'{endpoint}/?{querystring}'


def filter_results(response):
    results = response['results']
    return [
        result for result in results
        if (result.get('access_restricted') == False and
            isinstance(result.get('online_format'), list) and
            'online text' in result.get('online_format')) and
            'english' in result.get('language') and
            'blogs.loc.gov' not in urlparse(result.get('id')).netloc
    ]


def paginate_search(url):
    next_page = True
    page = 1    # LC pagination is 1-indexed
    http = http_adapter()

    while next_page:
        current_url = f'{url}&sp={page}'
        response = http.get(current_url, timeout=TIMEOUT).json()

        page += 1
        next_page = response['pagination']['next']  # Will be null when done
        time.sleep(0.3)  # respect rate limit

        yield response


def filenamify(result):
    name = result['id']
    name = name.split('/')
    # will strip null string after trailing slash if present
    name = [x for x in name if x]
    return f'results/{name[-1]}'


def slurp(**kwargs):
    '''
    Given a query parameters matching the LocUrl options, queries the Library of
    Congress API for text documents matching that term.

    When run with as_iterator=True, will yield the documents one by one (along
    with their LOC ID), as well as collecting summary statistics. When run with
    as_iterator=False (the default), will only collect summary statistics.
    '''
    logging.basicConfig(filename=f'slurp_{timestamp}.log')

    kwargs['q'] = kwargs['query']
    url = LocUrl(**kwargs).construct()
    stats = defaultdict(int)

    progress = 0
    for response in paginate_search(url):
        results = filter_results(response)
        print(f'Processing {len(results)} usable results...')
        for result in results:
            stats['processed'] += 1
            if stats['processed'] % 100 == 0:
                print(f'...{stats["processed"]} processed')
            try:
                text = Fetcher(result).full_text()
                if text:
                    stats['found'] += 1
                    stats['total_words'] += len(text.split(' '))
                    # if kwargs.get('as_iterator'):
                    #     yield (result["id"], text)
                    with open(filenamify(result), 'w') as f:
                        f.write(text)

                else:
                    logging.warning(f'WAT: Could not locate text for {result["id"]}')
                    stats['not_found'] += 1
            except UnknownIdentifier:
                logging.exception(f'UNK: Could not find identifier for {result["id"]} with image_url {result["image_url"]}')
                stats['failed'] += 1
            except Exception as err:
                logging.exception(f'BAD: Failed on {result["id"]} with image_url {result["image_url"]}')
                stats['failed'] += 1

    print(f'{stats["processed"]} processed, {stats["found"]} texts found with {stats["total_words"]} total words, {stats["not_found"]} not found, {stats["failed"]} failed, of {response["pagination"]["of"]} total')


if __name__ == '__main__':
    slurp()
