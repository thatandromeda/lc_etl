from time import sleep
from urllib.parse import urlparse

import requests

from lc_text_fetcher import Fetcher, UnknownIdentifier

PAGE_LENGTH = 100

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
        url = f'{url}&sp={page}'
        response = requests.get(url).json()
        page += 1
        next_page = response['pagination']['next']  # Will be null when done
        sleep(0.3)  # respect rate limit
        yield response


def slurp(subject='african americans'):
    url = build_url(subject)
    for response in paginate_search(url):
        results = filter_results(response)
        for result in results:
            try:
                Fetcher().full_text(result)
            except UnknownIdentifier:
                print(f'cannot find identifier for {result["image_url"]}')
            except Exception as err:
                print(err)
