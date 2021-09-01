# For now, let's just write it to files -- we'll set up db infrastructure when
# requirements stabilize a bit.

import json
from pathlib import Path

from queries import http_adapter

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

# iterate through results
# parse identifier
# issue API call
# write file
# TODO
#   - find out what kinds of date results I can get and standardize them
#   - can I batch API calls for efficiency?
#   - register handlers for the columns somewhere so you can DRY out initialize_csv and the item loop
#   - incrementally write json
results_path = Path('results')
results_metadata = {}

for item in results_path.iterdir():
    # Get the item as json
    identifier = item.parts[-1]
    response = http.get(f'https://www.loc.gov/item/{identifier}/?fo=json')
    try:
        item_json = response.json()['item']
    except (KeyError, json.decoder.JSONDecodeError):
        with open('failed_calls.txt', 'a') as f:
            f.write(identifier)
        continue

    if not item_json:
        with open('failed_calls.txt', 'a') as f:
            f.write(identifier)
        continue

    metadata = {}

    # Get the metadata. Any of these may be None.
    metadata['collections'] = get_collections(item_json)    # list of strings
    metadata['title'] = item_json.get('title')              # string
    metadata['image_url'] = get_image(item_json)            # string
    # string, could be YYYY or YYYY-MM-DD
    metadata['date'] = item_json.get('date')
    # dict of 'subject': 'url to subject search' pairs.
    metadata['subjects'] = item_json.get('subjects')
    metadata['subject_headings'] = item_json.get('subject_headings')  # list of strings
    metadata['locations'] = get_locations(item_json)
    metadata['url'] = item_json.get('url')                  # string

    results_metadata[identifier] = metadata

with open('results_metadata.txt', 'w') as f:
    json.dump(results_metadata, f)

# iterate through newspapers
# parse identifier
# issue API call
#   - the item URL is just the ChronAm URL (like the filepath) but with .json
#   - it isn't useful though; the /lccn/{identifier}.json has a little more
#   - better than either of these is the regular API call
#   - which means the thing to do is pull out the logic above and call it from
#     an results iterator and a newspapers iterator, with different identifier
#     logic
# write file
#   - actually, we're going to want a db at this point
#   - although we can consider feather, if that works better with the viz:
#     https://arrow.apache.org/docs/python/json.html
