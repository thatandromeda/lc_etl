# For now, let's just write it to files -- we'll set up db infrastructure when
# requirements stabilize a bit.

from argparse import ArgumentParser
import json
import logging
from pathlib import Path
import re
import shutil

from queries import http_adapter, make_timestamp

http = http_adapter()
OUTPUT_DIR = 'metadata'
Path(OUTPUT_DIR).mkdir(exist_ok=True)
logging.basicConfig(filename=f'{OUTPUT_DIR}/{make_timestamp()}.log',
                    format="%(asctime)s:%(levelname)s:%(message)s",
                    level=logging.INFO)

parser = ArgumentParser()
parser.add_argument('--identifiers',
                    help='path to metadata file output by embedding.py',
                    required=True)
options = parser.parse_args()

def get_collections(json):
    try:
        options = json['partof']
        return [
            x['title'] for x in item_json['partof'] if '/collections/' in x['url']
        ]
    except KeyError:
        return None


# Unlike other get_metadata functions, this returns only the first rather than
# every image_url. I think they are just different-size variants of the same
# image, and there is no particular reason to prefer one over the other at
# this time.
def get_image(json):
    try:
        image_urls = json['image_url']
        return image_urls[0]
    except KeyError:
        return None


def get_locations(json):
    try:
        locations = json['location']
        # Deduplicate; the API documents explicitly warn this value may
        # contain duplicates
        return list(set(locations))
    except KeyError:
        return None


def parse_identifier(item):
    return item.parts[-1]


CACHE = {}
def get_item_json(identifier):
    # Get the item as json
    if identifier in CACHE:
        # Different editions/pages of a newspaper have the same identifier,
        # so let's cache those results rather than hitting the server a
        # lot of times.
        item_json = CACHE[identifier]
    else:
        response = http.get(f'https://www.loc.gov/item/{identifier}/?fo=json')
        try:
            item_json = response.json()['item']
            CACHE[identifier] = item_json
        except (KeyError, json.decoder.JSONDecodeError):
            with open('failed_calls.txt', 'a') as f:
                f.write(identifier)
            return None

        if not item_json:
            with open('failed_calls.txt', 'a') as f:
                f.write(identifier)
            return None

    return item_json

# We need this later in zip_csv to write the csv correctly. Don't deviate from
# this order (or if you do, add some handling in zip_csv to make sure items
# are being written correctly).
METADATA_ORDER = [
    'collections', 'title', 'subjects', 'subject_headings', 'locations', 'date',
    'url', 'image_url', 'description'
]
def parse_item_metadata(item_json):
    metadata = {}

    # Get the metadata. Any of these may be None.
    metadata['collections'] = get_collections(item_json)    # list of strings
    metadata['title'] = item_json.get('title')              # string
    # dict of 'subject': 'url to subject search' pairs.
    metadata['subjects'] = item_json.get('subjects')
    metadata['subject_headings'] = item_json.get('subject_headings')  # list of strings
    metadata['locations'] = get_locations(item_json)
    metadata['description'] = item_json.get('description')

    return metadata


def add_newspaper_info(metadata, idx):
    metadata['date'] = date_from_chronam_identifier(idx)    # YYYY-MM-DD
    url = url_from_chronam_identifier(idx)
    metadata['url'] = url    # string
    # string; guessing rather than API round-tripping; seems usually right
    metadata['image_url'] = f'{url}.jp2'
    return metadata


def add_results_info(metadata, item_json):
    metadata['date'] = item_json.get('date')                # YYYY or YYYY-MM-DD
    metadata['url'] = item_json.get('url')                  # string
    metadata['image_url'] = get_image(item_json)            # string
    return metadata


newspaper_pattern = re.compile('(\w+)/\d{4}/\d{2}/\d{2}/ed-\d/seq-\d')
def is_chronam(idx):
    return bool(newspaper_pattern.match(idx))


def identifier_from_chronam(idx):
    return newspaper_pattern.match(idx).group(1).strip()


date_pattern = re.compile(r'(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})')
def url_from_chronam_identifier(idx):
    # We expect things like sn85025202/1865/01/14/ed-1/seq-2 .
    improved_idx = re.sub(
        date_pattern,
        r'\g<year>-\g<month>-\g<day>',
        idx,
    )
    return f'https://chroniclingamerica.loc.gov/lccn/{improved_idx}'


def date_from_chronam_identifier(idx):
    date_matches = date_pattern.search(idx)
    return f'{date_matches.group("year")}-{date_matches.group("month")}-{date_matches.group("day")}'


# iterate through results
# parse identifier
# issue API call
# write file
# TODO
#   - find out what kinds of date results I can get and standardize them
#   - can I batch API calls for efficiency?
#   - register handlers for the columns somewhere so you can DRY out initialize_csv and the item loop
#   - why is chronam date not matching

def fetch():
    with open(options.identifiers, 'r') as identifiers:
        results_metadata = {}

        next(identifiers)   # skip header row
        for idx in identifiers:
            print(f'Processing {idx}...')
            idx = idx.strip()
            try:
                if is_chronam(idx):
                    identifier = identifier_from_chronam(idx)
                    item_json = get_item_json(identifier)
                    metadata = parse_item_metadata(item_json)
                    metadata = add_newspaper_info(metadata, idx)
                    results_metadata[identifier] = metadata
                else:
                    # identifier == idx
                    item_json = get_item_json(idx)
                    metadata = parse_item_metadata(item_json)
                    metadata = add_results_info(metadata, item_json)
                    results_metadata[idx] = metadata
            except:
                logging.exception("Couldn't get metadata")
                continue

            # ChronAm identifiers are whole directory structures, with the lccn for
            # the entire newspaper run at the top, followed by subdirectories for
            # dates and editions. We want to preserve this whole structure so that
            # different images from the same newspaper can have different metadata.
            # This means we need to ensure that the whole filepath exists, even
            # though we don't know how long it is.
            output_path = Path(OUTPUT_DIR) / idx
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open('w') as f:
                json.dump(results_metadata, f)

if __name__ == '__main__':
    fetch()
