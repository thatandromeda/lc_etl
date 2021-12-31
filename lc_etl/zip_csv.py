from argparse import ArgumentParser
import csv
import json
import logging
from pathlib import Path

from .assign_similarity_metadata import SCORE_NAMESPACE
from .fetch_metadata import METADATA_ORDER, OUTPUT_DIR, ChronAmMetadataFetcher
from .utilities import initialize_logger


def _get_score_keys(metadata):
    return list(metadata[SCORE_NAMESPACE].keys())


def _write_header(csv_output, score_keys):
    header = ['x', 'y'] + METADATA_ORDER + score_keys
    csv_output.writerow(header)


def extract_dict(identifier, metadata):
    if ChronAmMetadataFetcher.is_chronam(identifier):
        return metadata[ChronAmMetadataFetcher.extract_identifier(identifier)]

    return metadata[identifier]


def _zip_csv(coordinates, identifiers, output):
    logging.info('Starting to zip data')

    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    with open(output, 'w', newline='') as outfile:
        csv_output = csv.writer(outfile, delimiter=',')
        first_time_through = True

        with open(coordinates, 'r') as coords, open(identifiers, 'r') as identifiers:
            # Skip header rows
            next(coords)
            next(identifiers)

            for coordinate, identifier in zip(coords, identifiers):
                identifier = identifier.strip()

                try:
                    with open(OUTPUT_DIR / Path(identifier)) as f:
                        raw_item_metadata = json.load(f)

                    item_metadata = extract_dict(identifier, raw_item_metadata)

                    if first_time_through:
                        score_keys = _get_score_keys(item_metadata)
                        _write_header(csv_output, score_keys)
                        first_time_through = False

                    output = [item_metadata.get(key) for key in METADATA_ORDER]
                    scores = [item_metadata[SCORE_NAMESPACE].get(key) for key in score_keys]

                    output = output + scores
                except (KeyError, json.JSONDecodeError) as e:
                    # Sometimes we didn't successfully fetch the metadata.
                    logging.exception(f"Couldn't zip metadata for {identifier}")
                    continue
                except FileNotFoundError:
                    logging.exception(f"No metadata file present for {identifier}")
                    continue

                output = coordinate.strip().split(',') + output

                csv_output.writerow(output)

    logging.info('Done zipping data')


def run(coordinates, identifiers, output, logfile='zip_csv.log'):
    initialize_logger(logfile)

    _zip_csv(coordinates, identifiers, output)
