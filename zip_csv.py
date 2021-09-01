# iterate through model coordinates
# also iterate through model metadata
import csv
import json

with open('results_metadata.txt', 'r') as f:
    metadata = json.load(f)

columns = list(iter(metadata.values()).__next__().keys())

header = ['x', 'y'] + columns

with open('viz/labeled_model.csv', 'w', newline='') as f:
    csv_output = csv.writer(f, delimiter=',')
    csv_output.writerow(header)
    with open('viz/model_20210824_132017_coordinates.csv', 'r') as coords, open('viz/model_20210824_132017_metadata.csv', 'r') as identifiers:
        # Skip header rows
        next(coords)
        next(identifiers)

        for coordinate, identifier in zip(coords, identifiers):
            try:
                raw_item_metadata = metadata[identifier.strip()]
                raw_item_metadata = [str(x) for x in list(raw_item_metadata.values())]
            except KeyError as e:
                # ChronAm items aren't in this file yet
                raw_item_metadata = [''] * (len(header) - 2)

            item_metadata = coordinate.strip().split(',') + raw_item_metadata

            csv_output.writerow(item_metadata)
