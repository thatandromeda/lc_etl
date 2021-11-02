from argparse import ArgumentParser
import importlib
import logging

from locr import Fetcher

from lc_items import slurp_items
from lc_collections import slurp_collections
from newspapers import slurp_newspapers
from queries import slurp, initialize_logger


def normalize(dataset_path):
    return dataset_path.replace('.py', '').replace('dataset_definitions/', '')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--dataset_path',
        help='dataset name. This should be a file in dataset_definitions that contains lists of collections, date-filtered collections, queries, and items to pull from LOC. The lists may be empty.')
    parser.add_argument('--logfile', help='name of log file', default="dataset.log")
    options = parser.parse_args()

    initialize_logger(options.logfile)

    data_def = __import__(
        f'dataset_definitions.{normalize(options.dataset_path)}',
        fromlist=['collections', 'date_filtered_collections', 'items', 'queries']
    )

    if data_def.collections:
        logging.info('Fetching data from collections...')
        slurp_collections(data_def.collections)
    else:
        logging.info('No collections defined.')

    if data_def.date_filtered_collections:
        logging.info('Fetching data from date-filtered collections...')
        slurp_collections(data_def.date_filtered_collections, filter_for_dates=True)
    else:
        logging.info('No date-filtered collections defined.')

    if data_def.queries:
        logging.info('Fetching data from queries...')
        for query in data_def.queries:
            logging.info(query)
            slurp(url=query)
    else:
        logging.info('No queries defined.')

    if data_def.items:
        logging.info('Fetching data from items...')
        slurp_items(data_def.items)
    else:
        logging.info('No items defined.')

    logging.info('Fetching data from ChronAm...')
    slurp_newspapers()
