# Originally, I only included the date in the metadata. However, we want to use
# year to color dots in the visualization, so it needs to be added to the
# metadata. This is a quick one-off script to do that.

import glob
import json
import logging
from pathlib import Path

from .utilities import initialize_logger

def _get_meta_metadata(txt_file, metadata_dir, data_dir):
    txt_file = str(txt_file)
    if 'ocr.txt' in txt_file:
        # This converts something like `newspaper_dir/lccn/path/to/file` into
        # `lccn/path/to/file`. This simplifies accessing the metadata, even though
        # we need the original path to access the fulltext file.
        txt_path = txt_file.replace('ocr.txt', '').replace(data_dir, '').lstrip('/')
        metadata_path = Path(metadata_dir) / txt_path
        idx = txt_path.split('/')[0]
    else:
        idx = txt_file.split('/')[-1]
        metadata_path = Path(metadata_dir) / idx

    return metadata_path, idx


def _add_year(metadata_dir, data_dir, iterator):
    count = 0

    for txt_file in iterator:
        count += 1
        output_path, idx = _get_meta_metadata(txt_file, metadata_dir, data_dir)

        if not output_path.is_file():
            logging.warning(f'Metadata file does not exist at {output_path}')
            continue

        logging.info(f'Adding year metadata for {txt_file}...')

        with output_path.open('r') as f:
            try:
                metadata = json.load(f)
            except json.decoder.JSONDecodeError:
                logging.exception(f'Malformed metadata')
                continue

        metadata[idx]['year'] = metadata[idx]['date'][:4]

        with output_path.open('w') as f:
            json.dump(metadata, f)

        if count % 100 == 0:
            logging.info(f'{count} files processed for year addition')


def run(metadata_dir, newspaper_dir=None, results_dir=None, logfile='add_year.log'):
    initialize_logger(logfile)

    if newspaper_dir:
        logging.info('Processing newspapers...')
        _add_year(metadata_dir, newspaper_dir, Path(newspaper_dir).rglob('**/*.txt'))

    if results_dir:
        logging.info('Processing non-newspapers...')
        _add_year(metadata_dir, results_dir, glob.iglob(f'{results_dir}/*'))
