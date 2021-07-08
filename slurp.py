from collections import defaultdict
import logging
import time
from urllib.parse import urlparse

import requests

from locr import Fetcher, UnknownIdentifier

timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())

PAGE_LENGTH = 100
TIMEOUT = 3

# Get around intermittent 500s or whatever.
retry = requests.packages.urllib3.util.retry.Retry(
    status=3, status_forcelist=[429, 500, 503]
)
adapter = requests.adapters.HTTPAdapter(max_retries=retry)
http = requests.Session()
http.mount("https://", adapter)
http.mount("http://", adapter)

def build_url(subject):
    subject = subject.replace(' ', '+')
    return 'https://www.loc.gov/search/?fo=json' \
           f'&fa=subject:{subject}' \
           '&fa=access-restricted:false' \
           '&fa=online-format:online-text' \
           f'&c={PAGE_LENGTH}' \


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

    while next_page:
        current_url = f'{url}&sp={page}'
        response = http.get(current_url, timeout=TIMEOUT).json()

        page += 1
        next_page = response['pagination']['next']  # Will be null when done
        time.sleep(0.3)  # respect rate limit

        yield response


def slurp(subject='african americans', as_iterator=False):
    '''
    Given a subject term, queries the Library of Congress API for text documents
    matching that term.

    When run with as_iterator=True, will yield the documents one by one (along
    with their LOC ID), as well as collecting summary statistics. When run with
    as_iterator=False (the default), will only collect summary statistics.
    '''
    logging.basicConfig(filename=f'slurp_{timestamp}.log')

    url = build_url(subject)
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
                if as_iterator:
                    yield (result["id"], text)

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
