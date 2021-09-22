# For now, let's just write it to files -- we'll set up db infrastructure when
# requirements stabilize a bit.

import json
from pathlib import Path
import re
import shutil

from queries import http_adapter, make_timestamp

http = http_adapter()

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


def parse_item_metadata(item_json):
    metadata = {}

    # Get the metadata. Any of these may be None.
    metadata['collections'] = get_collections(item_json)    # list of strings
    metadata['title'] = item_json.get('title')              # string
    # dict of 'subject': 'url to subject search' pairs.
    metadata['subjects'] = item_json.get('subjects')
    metadata['subject_headings'] = item_json.get('subject_headings')  # list of strings
    metadata['locations'] = get_locations(item_json)

    return metadata


def add_newspaper_info(metadata, idx):
    metadata['date'] = date_from_chronam_identifier(idx)    # YYYY-MM-DD
    metadata['url'] = url_from_chronam_identifier(idx)      # string
    # string; guessing rather than API round-tripping; seems usually right
    metadata['image_url'] = idx.strip().rstrip('/') + '.jp2'
    return metadata


def add_results_metadata(metadata, item_json):
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

RESULTS_FILE = 'results_metadata.txt'
BACKUP_RESULTS_FILE = f'results_metadata.{make_timestamp()}.txt'

# Our json items will need to be enclosed in square brackets to form a valid
# list, so let's start by initializing this. (The alternative would be keeping
# the entire json object in memory as we add more metadata to it and writing
# it when done, or overwriting it on every iteration; we'd get validity for
# free but gosh is that slow-sounding.)
# Note that this one *writes* (hence overwrites), but all others *append*.
with open(RESULTS_FILE, 'w') as f:
    f.write('[')

with open('viz/model_20210824_132017_metadata.csv', 'r') as identifiers:
    results_metadata = {}

    is_first_iteration = True

    next(identifiers)   # skip header row
    for idx in identifiers:
        print(f'Processing {idx}...')
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
            import pdb; pdb.set_trace()

        with open(RESULTS_FILE, 'a') as f:
            # We need to comma-separate our json items for the entire result
            # to be valid json. However, if we add a comma after the last one,
            # it will be invalid. Therefore, we add a comma *before* every item
            # *except* the first one.
            if not is_first_iteration:
                f.write(',')
            json.dump(results_metadata, f)

        is_first_iteration = False

    # Close list so we have valid json.
    with open(RESULTS_FILE, 'a') as f:
        f.write(']')

    # Copy to a backup location, since we will always replace results_metadata
    # with the latest version.
    shutil.copy(RESULTS_FILE, BACKUP_RESULTS_FILE)
