# For now, let's just write it to files -- we'll set up db infrastructure when
# requirements stabilize a bit.

from argparse import ArgumentParser
import glob
import json
import logging
from pathlib import Path
import re
import shutil
from time import sleep

from utilities import http_adapter, make_timestamp, initialize_logger, BASE_DIR


# We need this later in zip_csv to write the csv correctly. Don't deviate from
# this order (or if you do, add some handling in zip_csv to make sure items
# are being written correctly).
METADATA_ORDER = [
    'collections', 'title', 'subjects', 'subject_headings', 'locations', 'date',
    'url', 'image_url', 'description', 'states'
]

OUTPUT_DIR = f'{BASE_DIR}/metadata'
STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas' 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana', 'Maine',
    'Maryland', 'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi',
    'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire', 'New Jersey',
    'New Mexico', 'New York', 'North Carolina', 'North Dakota', 'Ohio',
    'Oklahoma', 'Oregon', 'Pennsylvania', 'Rhode Island', 'South Carolina',
    'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia',
    'Washington', 'West Virginia', 'Wisconsin', 'Wyoming'
}

class NoMetadataFound(Exception):
    pass


class BaseMetadataFetcher(object):
    """Parent class containing shared logic for retrieving metadata for both
    ChronAm and regular LOC items. Logic specific to one object type belongs
    in subclasses."""

    newspaper_pattern = re.compile('(\w+)/\d{4}/\d{2}/\d{2}/ed-\d/seq-\d')
    date_pattern = re.compile(r'(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})')

    def __init__(self):
        self.http = http_adapter()
        self.json = None
        self.cache = {}
        self.identifier = None
        self.metadata = {}

        Path(OUTPUT_DIR).mkdir(exist_ok=True)

    @classmethod
    def is_chronam(cls, idx):
        return bool(cls.newspaper_pattern.search(idx))


    def get_collections(self):
        try:
            options = self.json['partof']
            return [
                x['title'] for x in options if '/collections/' in x['url']
            ]
        except KeyError:
            return None


    # Unlike other get_metadata functions, this returns only the first rather than
    # every image_url. I think they are just different-size variants of the same
    # image, and there is no particular reason to prefer one over the other at
    # this time.
    def get_image(self):
        try:
            image_urls = self.json['image_url']
            return image_urls[0]
        except KeyError:
            return None


    def get_locations(self):
        try:
            locations = self.json['location']
            # Deduplicate; the API documents explicitly warn this value may
            # contain duplicates
            return list(set(locations))
        except KeyError:
            return []


    def get_states(self):
        locations = self.metadata['locations']
        standardized_locations = [location.title() for location in locations]
        return list(STATES.intersection(set(standardized_locations)))


    def parse_identifier(item):
        return item.parts[-1]


    def set_item_json(self):
        # Get the item as json
        if self.identifier in self.cache:
            # Different editions/pages of a newspaper have the same identifier,
            # so let's cache those results rather than hitting the server a
            # lot of times.
            item_json = self.cache[self.identifier]
        else:
            with self.http as h:
                response = h.get(f'https://www.loc.gov/item/{self.identifier}/?fo=json')
            sleep(0.5)  # rate limits
            try:
                item_json = response.json()['item']
                self.cache[self.identifier] = item_json
            except (KeyError, json.decoder.JSONDecodeError):
                with open('failed_calls.txt', 'a') as f:
                    f.write(f"{self.identifier}\n")

        try:
            self.json = item_json
        except NameError:
            with open('failed_calls.txt', 'a') as f:
                f.write(f"{self.identifier}\n")
            raise NoMetadataFound


    def parse_item_metadata(self):
        # Get the metadata. Any of these may be None.
        self.metadata['collections'] = self.get_collections()    # list of strings
        self.metadata['title'] = self.json.get('title')              # string
        # dict of 'subject': 'url to subject search' pairs.
        self.metadata['subjects'] = self.json.get('subjects')
        self.metadata['subject_headings'] = self.json.get('subject_headings')  # list of strings
        self.metadata['locations'] = self.get_locations()
        self.metadata['description'] = self.json.get('description')
        self.metadata['states'] = self.get_states()
        self.metadata['keyword_scores'] = {}  # set by assign_similarity_metadata


    def fetch(self):
        self.set_identifier()
        self.set_item_json()
        self.parse_item_metadata()


class ChronAmMetadataFetcher(BaseMetadataFetcher):
    """Contains logic for retriving metadata which is specific to ChronAm
    objects."""


    def __init__(self, cache, idx):
        super(ChronAmMetadataFetcher, self).__init__()
        self.cache = cache
        self.idx = idx


    @classmethod
    def extract_identifier(cls, idx):
        return cls.newspaper_pattern.search(idx).group(1).strip()


    def extract_path(self):
        before, after = self.idx.split(self.extract_identifier(self.idx))
        return self.idx.replace(before, '').replace('ocr.txt', '')


    def add_newspaper_info(self):
        self.metadata['date'] = self.date_from_chronam_identifier()    # YYYY-MM-DD
        url = self.url_from_chronam_identifier()
        self.metadata['url'] = url    # string
        # This is a guess, based on contents of HTML pages,  since it isn't in
        # the info returned by the API. The 'jp2' field triggers a download
        # rather than providing a usable image directly.
        # We use Path as a hack because it will do the right thing whether or
        # not there's a trailing slash.
        self.metadata['image_url'] = str(Path(url) / 'thumbnail.jpg')


    def set_identifier(self):
        self.identifier = self.extract_identifier(self.idx)


    def date_from_chronam_identifier(self):
        date_matches = self.date_pattern.search(self.idx)
        return f'{date_matches.group("year")}-{date_matches.group("month")}-{date_matches.group("day")}'


    def url_from_chronam_identifier(self):
        # We expect things like sn85025202/1865/01/14/ed-1/seq-2 .
        improved_idx = re.sub(
            self.date_pattern,
            r'\g<year>-\g<month>-\g<day>',
            self.extract_path(),
        )
        return f'https://chroniclingamerica.loc.gov/lccn/{improved_idx}'


    def fetch(self):
        super(ChronAmMetadataFetcher, self).fetch()
        self.add_newspaper_info()
        return {self.identifier: self.metadata}


class ItemMetadataFetcher(BaseMetadataFetcher):
    """Contains logic for retriving metadata which is specific to ordinary LOC
    objects."""

    def __init__(self, cache, idx):
        super(ItemMetadataFetcher, self).__init__()
        self.cache = cache
        self.idx = idx


    def add_results_info(self):
        self.metadata['date'] = self.json.get('date')            # YYYY or YYYY-MM-DD
        self.metadata['url'] = self.json.get('url')              # string
        self.metadata['image_url'] = self.get_image()            # string


    @classmethod
    def extract_identifier(cls, idx):
        return Path(idx).name


    def extract_path(self):
        return self.extract_identifier(self.idx)


    def set_identifier(self):
        self.identifier = self.extract_identifier(self.idx)


    def fetch(self):
        super(ItemMetadataFetcher, self).fetch()
        self.add_results_info()
        return {self.identifier: self.metadata}


# iterate through results
# parse identifier
# issue API call
# write file
# TODO
#   - find out what kinds of date results I can get and standardize them
#   - can I batch API calls for efficiency?
#   - register handlers for the columns somewhere so you can DRY out initialize_csv and the item loop
#   - why is chronam date not matching


def _inner_fetch(identifiers, overwrite):
    """
    Takes an iterable of LC identifiers and fetches their metadata.
    """
    cache = {}

    for idx in identifiers:
        results_metadata = {}
        idx = idx.strip()
        logging.info(f'Processing {idx}...')

        if BaseMetadataFetcher.is_chronam(idx):
            fetcher = ChronAmMetadataFetcher(cache, idx)
        else:
            fetcher = ItemMetadataFetcher(cache, idx)

        idx_path = fetcher.extract_path()

        # ChronAm identifiers are whole directory structures, with the lccn for
        # the entire newspaper run at the top, followed by subdirectories for
        # dates and editions. We want to preserve this whole structure so that
        # different images from the same newspaper can have different metadata.
        # This means we need to ensure that the whole filepath exists, even
        # though we don't know how long it is.
        output_path = Path(OUTPUT_DIR) / idx_path

        # If we have already downloaded this metadata, don't bother doing
        # it again.
        if Path(output_path).is_file() and not overwrite:
            logging.info(f'{output_path} found, not fetching')
            continue

        try:
            logging.info(f'Downloading new data for {idx}')
            result = fetcher.fetch()
        except:
            logging.exception(f"Couldn't get metadata for {idx}")
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w') as f:
            json.dump(result, f)


def fetch(options):
    """
    Fetches metadata for ALL identifiers passed in by any of the following
    options: identifiers, newspaper_dir, results_dir.
    If the same identifier is found in multiple places, it will be cached
    from the first time and not refetched.
    """

    overwrite = bool(options.overwrite)

    if options.identifiers:
        with open(options.identifiers, 'r') as identifiers:
            next(identifiers)   # skip header row

            _inner_fetch(identifiers, overwrite)

    # Don't do try/except here! The glob statement will work even if
    # options.newspaper_dir is None; it will just search your entire computer,
    # from / .
    if options.newspaper_dir:
        _inner_fetch(glob.iglob(
            f'{options.newspaper_dir}/**/ocr.txt', recursive=True
        ), overwrite)

    if options.results_dir:
        _inner_fetch(glob.iglob(f'{options.results_dir}/*'), overwrite)


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--identifiers',
                        help='path to metadata file output by embedding.py')
    parser.add_argument('--newspaper_dir',
                        help='path to newspaper files')
    parser.add_argument('--results_dir',
                        help='path to non-newspaper files')
    parser.add_argument('--logfile', default="fetch_metadata.log")
    parser.add_argument('--overwrite', default=False)

    return parser.parse_args()


if __name__ == '__main__':
    options = parse_args()

    if not any([options.identifiers, options.newspaper_dir, options.results_dir]):
        print('Must provide at least one source of identifiers')
        import sys; sys.exit()

    initialize_logger(options.logfile)

    fetch(options)
