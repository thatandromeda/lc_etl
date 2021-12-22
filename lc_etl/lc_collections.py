import logging
from urllib.parse import urlparse

from locr import Fetcher
from locr.exceptions import AmbiguousText, ObjectNotOnline
import requests

from utilities import paginate_search, filter_results, filenamify

def slurp_collections(collections, filter_for_dates=False):
    found = 0
    total_words = 0
    total_docs = 0
    for base_url in collections:
        logging.info(f'PROCESSING: {base_url}')
        last_found = found
        last_words = total_words

        url = f'{base_url}search/?fa=online-format:online+text&fo=json'
        if filter_for_dates:
            url += '&dates=1863/1877'

        for response in paginate_search(url):
            results = filter_results(response)
            for result in results:
                total_docs += 1
                try:
                    fetcher = Fetcher(result)

                    try:
                        text = fetcher.full_text()
                    except (AmbiguousText, ObjectNotOnline):
                        logging.exception(f'Could not get text for {url}')
                        continue

                    if text:
                        found += 1
                        total_words += len(text.split(' '))

                        with open(filenamify(result), 'w') as f:
                            f.write(text)
                except:
                    logging.warning(f'WAT: Could not locate text for {result["id"]}')

        logging.info(f'for collection {base_url}...')
        logging.info(f'{found-last_found} documents found; {total_words-last_words} words')

    logging.info(f'{found} documents found of {total_docs} total; {total_words} total words')
