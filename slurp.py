import logging
from time import sleep
from urllib.parse import urlparse

import requests

from lc_text_fetcher import Fetcher, UnknownIdentifier

logging.basicConfig(filename='bad_results.log')

PAGE_LENGTH = 100

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
        response = http.get(current_url).json()

        page += 1
        next_page = response['pagination']['next']  # Will be null when done
        sleep(0.3)  # respect rate limit

        yield response


def slurp(subject='african americans'):
    url = build_url(subject)
    processed = 0
    failed = 0

    for response in paginate_search(url):
        results = filter_results(response)
        for result in results:
            try:
                Fetcher(result).full_text()
                processed += 1
            except UnknownIdentifier:
                logging.exception(f'UNK: Could not find identifier for {result["id"]} with image_url {result["image_url"]}')
                failed += 1
            except Exception as err:
                logging.exception(f'BAD: Failed on {result["id"]} with image_url {result["image_url"]}')
                failed += 1

    print(f'{processed} processed, {failed} failed, of {response["pagination"]["of"]} total')

if __name__ == '__main__':
    slurp()
