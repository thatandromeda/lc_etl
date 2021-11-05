from argparse import ArgumentParser
import csv
import json
import logging
from pathlib import Path

from fetch_metadata import METADATA_ORDER, OUTPUT_DIR, is_chronam, identifier_from_chronam
from queries import initialize_logger

Path(OUTPUT_DIR).mkdir(exist_ok=True)

parser = ArgumentParser()
parser.add_argument('--coordinates', help='path/to/coordinates/file', required=True)
parser.add_argument('--identifiers', help='path/to/identifiers/file', required=True)
parser.add_argument('--output', help='path/to/output/file', required=True)
parser.add_argument('--logfile', default="zip_csv.log")
options = parser.parse_args()

initialize_logger(options.logfile)

header = ['x', 'y'] + METADATA_ORDER

logging.info('Starting to zip data')
with open(options.output, 'w', newline='') as outfile:
    csv_output = csv.writer(outfile, delimiter=',')
    csv_output.writerow(header)
    with open(options.coordinates, 'r') as coords, open(options.identifiers, 'r') as identifiers:
        # Skip header rows
        next(coords)
        next(identifiers)

        for coordinate, identifier in zip(coords, identifiers):
            identifier = identifier.strip()
            try:
                with open(OUTPUT_DIR / Path(identifier)) as f:
                    raw_item_metadata = json.load(f)

                item_metadata = [raw_item_metadata.get(key) for key in METADATA_ORDER]
            except (KeyError, json.JSONDecodeError) as e:
                # Sometimes we didn't successfully fetch the metadata.
                logging.exception(f"Couldn't zip metadata for {identifier}")
                continue
            except FileNotFoundError:
                logging.exception(f"No metadata file present for {identifier}")
                continue

            item_metadata = coordinate.strip().split(',') + item_metadata

            csv_output.writerow(item_metadata)

logging.info('Done zipping data')
