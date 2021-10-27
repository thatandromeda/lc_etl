from argparse import ArgumentParser
import csv
import json
import logging
from pathlib import Path

from fetch_metadata import METADATA_ORDER, OUTPUT_DIR, is_chronam, identifier_from_chronam
from queries import make_timestamp

Path(OUTPUT_DIR).mkdir(exist_ok=True)
logging.basicConfig(filename=f'{OUTPUT_DIR}/zip_{make_timestamp()}.log',
                    format="%(asctime)s:%(levelname)s:%(message)s",
                    level=logging.INFO)

parser = ArgumentParser()
parser.add_argument('--coordinates', help='path/to/coordinates/file', required=True)
parser.add_argument('--metadata', help='path/to/metadata/file', required=True)
parser.add_argument('--output', help='path/to/output/file', required=True)
options = parser.parse_args()

header = ['x', 'y'] + METADATA_ORDER

def extract_dict(identifier, metadata):
    if is_chronam(identifier):
        return metadata[identifier_from_chronam(identifier)]

    return metadata[identifier]

with open(options.output, 'w', newline='') as outfile:
    csv_output = csv.writer(outfile, delimiter=',')
    csv_output.writerow(header)
    with open(options.coordinates, 'r') as coords, open(options.metadata, 'r') as identifiers:
        # Skip header rows
        next(coords)
        next(identifiers)

        for coordinate, identifier in zip(coords, identifiers):
            try:
                with open(OUTPUT_DIR / Path(identifier.strip())) as f:
                    raw_item_metadata = json.load(f)

                item_metadata = extract_dict(identifier, raw_item_metadata)
                item_metadata = [item_metadata[key] for key in METADATA_ORDER]
            except (KeyError, json.JSONDecodeError) as e:
                # Sometimes we didn't successfully fetch the metadata.
                logging.exception(f"Couldn't zip metadata for {identifier}")
                continue

            item_metadata = coordinate.strip().split(',') + item_metadata

            csv_output.writerow(item_metadata)
