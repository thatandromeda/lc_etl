from argparse import ArgumentParser
import importlib
import logging
from pathlib import Path

from locr import Fetcher

from lc_items import slurp_items
from lc_collections import slurp_collections
from newspapers import slurp_newspapers
from utilities import slurp, initialize_logger, BASE_DIR


def normalize(dataset_path):
    return Path(dataset_path).parts[-1].replace('.py', '')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--dataset_path',
        help='dataset name. This should be a file in dataset_definitions that contains lists of collections, date-filtered collections, queries, and items to pull from LOC. The lists may be empty.')
    parser.add_argument('--logfile', help='name of log file', default="dataset.log")
    options = parser.parse_args()

    initialize_logger(options.logfile)

    data_def = __import__(
        f'dataset_definitions.{normalize(options.dataset_path)}',
        fromlist=['collections', 'date_filtered_collections', 'items', 'queries', 'newspapers']
    )

    try:
        logging.info('Fetching data from collections...')
        slurp_collections(data_def.collections)
    except AttributeError:
        logging.info('No collections defined.')

    try:
        logging.info('Fetching data from date-filtered collections...')
        slurp_collections(data_def.date_filtered_collections, filter_for_dates=True)
    except AttributeError:
        logging.info('No date-filtered collections defined.')

    try:
        logging.info('Fetching data from queries...')
        for query in data_def.queries:
            logging.info(query)
            slurp(url=query)
    except AttributeError:
        logging.info('No queries defined.')

    try:
        logging.info('Fetching data from items...')
        slurp_items(data_def.items)
    except AttributeError:
        logging.info('No items defined.')

    try:
        logging.info('Fetching data from ChronAm...')
        if data_def.newspapers.get('goal_dates'):
            slurp_newspapers(goal_dates=data_def.newspapers['goal_dates'])
        elif data_def.newspapers.get('count'):
            slurp_newspapers(count=data_def.newspapers['count'])
        else:
            slurp_newspapers()
    except AttributeError:
        logging.info('No newspapers defined')
