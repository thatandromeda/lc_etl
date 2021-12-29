# I think newspapers are clustering different issues of the same newspaper due
# to in-text references to nearby locations, and possibly to the title of the
# newspaper itself. Investigating word vectors within a test neural net shows
# that in fact it has learned similarities between locations, e.g.
#
# model.wv.most_similar('wilmington') [('baltimore', 0.6760503053665161), ('•',
# 0.6584498882293701), ('philadelphia', 0.6557695865631104), ('delaware',
# 0.6505554914474487), ('del', 0.6485189199447632), ('odessa',
# 0.6249222159385681), ('dover', 0.6067132949829102), ('milford',
# 0.5877234935760498), ('tbo', 0.5794641375541687), ('middletown',
# 0.5633726716041565)]
#
# model.wv.most_similar('delaware') [('dover', 0.7506685853004456), ('tbo',
# 0.6748696565628052), ('christiana', 0.6716688275337219), ('•',
# 0.6588472127914429), ('del', 0.6554073691368103), ('wilmington',
# 0.6505554914474487), ('pennsylvania', 0.6494061946868896), ('sussex',
# 0.6352145671844482), ('i«', 0.6254095435142517), ('tlio', 0.6142458915710449)]
#
# These are valid things to have learned but unhelpful for our purposes, as
# (e.g.) the Delaware Tribune of Wilmington, Delaware will likely refer to
# the locations "Wilmington" and "Delaware" much more than will (e.g.) the
# American Citizen of Canton, Mississippi, but I'm not interested in
# reproducing the clustering of newspapers by title; I'm interested in finding
# clusters, where, e.g., both the Tribune and the Citizen are talking about
# suffrage.
#
# Exploring the neural net shows that interesting concept words *also* cluster
# strongly; for example:
#
# model.wv.most_similar('equality')
# [('rights', 0.7068777084350586), ('suffrage', 0.6519492268562317),
# ('inalienable', 0.6133490800857544), ('social', 0.6014280319213867), ('socia',
# 0.5964685082435608), ('claring', 0.5723950862884521), ('freedom',
# 0.567748486995697), ('selfgovernment', 0.5670239925384521), ('tovote',
# 0.5653315782546997), ('privileges', 0.5635508298873901)]
#
# Therefore, I'd like to filter out title and place words, so that the neural
# net cannot include those. This means the window size gets a bit fuzzy (as
# I'll simply be dropping words), but I think that'll be OK.

# OK. I think they are clustering on places. I should make another filter which removes:
# - any words in the title of the newspaper
# - any words in the location metadata
# - (make sure to lowercase them first, or be case-insensitive)

from argparse import ArgumentParser
import json
import logging
from pathlib import Path
import string

from utilities import initialize_logger


def title_words(metadata):
    title = metadata.get('title')

    if not title:
        return []

    # This will probably remove words like "the". Is that bad?
    return [normalize(word) for word in title.split()]


def depunctuate(text):
    return text.translate(text.maketrans('', '', string.punctuation))


def normalize(word):
    return depunctuate(word.lower())


def locations(metadata):
    return [normalize(loc) for loc in metadata.get('locations')]


def get_stopwords(txt_file, target_dir, metadata_dir):
    metadata_file = str(txt_file).replace(target_dir, metadata_dir).replace('ocr.txt', '')
    with Path(metadata_file).open() as f:
        metadata = json.load(f)

    # Format of dict is { identifier: {data} }. So just getting the first values
    # object works for us. Yes, living on the edge here.
    metadata = next(iter(metadata.values()))
    stopwords = title_words(metadata) + locations(metadata)
    return list(set(stopwords))


def filter(target_dir, metadata_dir):
    count = 0
    for txt_file in Path(target_dir).rglob('**/*.txt'):
        count += 1
        try:
            stopwords = get_stopwords(txt_file, target_dir, metadata_dir)
        except FileNotFoundError:
            logging.exception(f'Metadata not found for {txt_file}')
            continue

        with open(txt_file, 'r') as f:
            text = f.read()

        filtered_text = normalize(text)
        for word in stopwords:
            filtered_text = filtered_text.replace(word, '')

        if count % 100 == 0:
            logging.info(f'{count} documents filtered')

        with open(txt_file, 'w') as f:
            f.write(filtered_text)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--target_dir', help='directory containing files to check')
    parser.add_argument('--metadata_dir', help='directory containing metadata for these files')
    parser.add_argument('--logfile', default="filter_newspaper_locations.log")

    options = parser.parse_args()

    initialize_logger(options.logfile)

    filter(options.target_dir.rstrip('/'), options.metadata_dir.rstrip('/'))
