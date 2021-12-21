from collections import defaultdict
import json
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import requests

from locr import Fetcher, UnknownIdentifier

def make_timestamp():
    return time.strftime('%Y%m%d_%H%M%S', time.localtime())


PAGE_LENGTH = 500
TIMEOUT = 3
BASE_DIR = 'lc_etl/data'

subprocess.call('mkdir results', shell=True)

def http_adapter():
    # Get around intermittent 500s or whatever. Unfortunately this opens a
    # socket that stays open, throwing ResourceWarnings during test. If you call
    # the adapter with a context manager, the session will close:
    # with http as h:
    #    response = h.get(whatever)
    retry = requests.packages.urllib3.util.retry.Retry(
        status=3, status_forcelist=[429, 500, 503]
    )
    adapter = requests.adapters.HTTPAdapter(max_retries=retry)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    return http


def initialize_logger(logfile):
    logging.basicConfig(filename=logfile,
                        filemode='a',
                        format="%(asctime)s:%(levelname)s:%(message)s",
                        level=logging.INFO)


class LocUrl(object):
    """docstring for LocUrl."""

    def __init__(self, **kwargs):
        super(LocUrl, self).__init__()
        self.collection = kwargs.get('collection')
        self.query = kwargs.get('q') or kwargs.get('query')
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
    emergency_exit = 0

    while next_page:
        current_url = f'{url}&sp={page}&c={PAGE_LENGTH}'
        try:
            response = http.get(current_url, timeout=TIMEOUT).json()
        except json.decoder.JSONDecodeError as e:
            logging.exception(f'Could not decode {current_url}')
            # Sometimes this error is intermittent -- we get a 5xx page instead
            # of JSON.
            emergency_exit += 1
            time.sleep(180)
            continue
        except requests.exceptions.ConnectionError:
            logging.exception(f'Timeout for {current_url}; waiting')
            time.sleep(180)
            emergency_exit += 1
            continue

        if emergency_exit >= 10:
            logger.warning('Quit search early due to excessive failures')
            break

        page += 1
        next_page = response['pagination']['next']  # Will be null when done
        time.sleep(0.3)  # respect rate limit

        yield response


def filenamify(result):
    name = result['id']
    name = name.split('/')
    # will strip null string after trailing slash if present
    name = [x for x in name if x]
    return str(Path(BASE_DIR) / 'results' / name[-1])


def jsonify(url):
    parsed_url = urlparse(url)
    if 'fo=json' not in parsed_url.query:
        # I can't believe python URL manipulation is this awful, but it is
        querydict = parse_qs(parsed_url.query)
        querydict.update({'fo': ['json']})
        new_url = [attr for attr in parsed_url]
        new_url[4] = urlencode(querydict, doseq=True)
        return urlunparse(new_url)
    else:
        return url


# By recording the subjects of processed items, we'll be able to use unix
# utilities later to see what the most common subjects are, and consider
# expanding our search accordingly.
def record_subjects(result):
    subjects_file = 'subjects.txt'
    subprocess.call(f'touch {subjects_file}', shell=True)

    with open(subjects_file, 'a') as f:
        for subject in (result.get('subject') or []):
            f.write(f'{subject}\n')


def check_for_disk_space():
    if shutil.disk_usage('/')[-1] < 1000000000:
        logging.info('Quitting for disk space!')
        logging.info(f'{stats["processed"]} processed, {stats["found"]} texts found with {stats["total_words"]} total words, {stats["not_found"]} not found, {stats["failed"]} failed, of {response["pagination"]["of"]} total')
        sys.exit()


def slurp(**kwargs):
    '''
    Queries the Library of Congress for text documents matching an API query.
    Can take the query URL directly (with a `url` argument), or will construct
    it from provided kwargs (see LocUrl for details). Provided URLs do not need
    to specify `fo=json`; this will be added if needed.

    When run with as_iterator=True, will yield the documents one by one (along
    with their LOC ID), as well as collecting summary statistics. When run with
    as_iterator=False (the default), will only collect summary statistics.
    '''
    try:
        url = jsonify(kwargs['url'])
    except KeyError:
        url = LocUrl(**kwargs).construct()
    stats = defaultdict(int)

    progress = 0
    for response in paginate_search(url):
        results = filter_results(response)
        logging.info(f'Processing {len(results)} usable results...')
        for result in results:
            record_subjects(result)
            stats['processed'] += 1
            if stats['processed'] % 100 == 0:
                logging.info(f'...{stats["processed"]} processed')
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

        check_for_disk_space()
    logging.info(f'{stats["processed"]} processed, {stats["found"]} texts found with {stats["total_words"]} total words, {stats["not_found"]} not found, {stats["failed"]} failed, of {response["pagination"]["of"]} total')


if __name__ == '__main__':
    slurp()
