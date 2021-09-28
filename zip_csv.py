import csv
import json
import logging
from pathlib import Path

from fetch_metadata import METADATA_ORDER, OUTPUT_DIR
from queries import make_timestamp

Path(OUTPUT_DIR).mkdir(exist_ok=True)
logging.basicConfig(filename=f'{OUTPUT_DIR}/zip_{make_timestamp()}.log',
                    format="%(asctime)s:%(levelname)s:%(message)s",
                    level=logging.INFO)

header = ['x', 'y'] + METADATA_ORDER

with open('viz/labeled_model.csv', 'w', newline='') as outfile:
    csv_output = csv.writer(outfile, delimiter=',')
    csv_output.writerow(header)
    with open('viz/model_20210824_132017_coordinates.csv', 'r') as coords, open('viz/model_20210824_132017_metadata.csv', 'r') as identifiers:
        # Skip header rows
        next(coords)
        next(identifiers)

        for coordinate, identifier in zip(coords, identifiers):
            try:
                with open(OUTPUT_DIR / Path(identifier.strip())) as f:
                    raw_item_metadata = json.load(f)
                raw_item_metadata = [str(x) for x in list(raw_item_metadata.values())]
            except (KeyError, json.JSONDecodeError) as e:
                # Sometimes we didn't successfully fetch the metadata.
                logging.exception(f"Couldn't zip metadata for {identifier}")
                continue

            item_metadata = coordinate.strip().split(',') + raw_item_metadata

            csv_output.writerow(item_metadata)
