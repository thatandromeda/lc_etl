"""
This script updates existing metadata to add scores for their corresponding
fulltext files' similarity to words in a given list of words. For instance, if
the word of interest is 'suffrage', this script will add an element like this to
metadata files:

{SCORE_NAMESPACE: {'suffrage': x}}

where SCORE_NAMESPACE is a string defined below and x is an integer representing
the similarity of 'suffrage' to the fulltext file in question.

The goal here is to allow for recoloring of the data visualization to show
files that are more or less "about" a particular word.

If the metadata file already has a SCORE_NAMESPACE element, it will be updated
with python's dict.update().

The score is calculated by:
- look at all words in a fulltext file >= MIN_WORD_LENGTH
- calculate their Word2Vec similarity to the desired word
- sum these similarities
- normalize to integer values between 0 and 100
"""
from argparse import ArgumentParser
import json
import glob
import logging
from pathlib import Path
import random

import gensim

from lc_etl.train_doc2vec import Configuration
from lc_etl.utilities import initialize_logger


# Based on experiments with a subset of newspapers and some words of interest:
# About 2/3 of the time, sampling 1/10th of the words in the text yields
# the same overall score. The vast majority of the time, it's within +/- 1.
# Naturally, this is also about 10x faster than looking at every word.
FRACTION = 0.1

# It's not worth calculating scores for short words, which will generally be
# irrelevant things like "the" and "and".
MIN_WORD_LENGTH = 4

# Word scores will be stored within the main metadata dict under this key,
# to prevent any accidental namespace collisions with other metadata keys,
# and to keep the metadata orderly. Thus the overall structure will be
# metadata = {lccn: { SCORE_NAMESPACE: {'word_1': score, ...}, ..other metadata...}}
SCORE_NAMESPACE = 'keyword_scores'


def _single_word_score(model, base_words, word):
    scores = {}

    for base_word in base_words:
        try:
            score = model.wv.similarity(base_word, word)
        except KeyError:
            score = 0

        scores[base_word] = score

    return scores


def sample_words(text):
    # Discard short words like 'and' as they won't contribute meaningfully
    # but will take time to process.
    words = [word for word in Configuration.tokenize(text) if len(word) >= MIN_WORD_LENGTH]

    # Return a random tenth of the remaining words.
    return random.sample(words, round(len(words)*FRACTION))


def _derive_scores(model, txt_file, base_words):
    """
    Takes a model, a text file, and a list of base words.

    Returns a dict of {base_word: score}, where score is an integer between 0
    and 100 which represents the average similarity of the text to the given
    word.
    """
    with open(txt_file, 'r') as f:
        text = f.read()

    words = sample_words(text)
    # This is a list of dicts of the form {base_word: score}.
    raw_scores = [_single_word_score(model, base_words, word) for word in words]

    summed_scores = {}
    for base_word in base_words:
        summed_scores[base_word] = sum([item[base_word] for item in raw_scores])
        summed_scores[base_word] = round(
            100 * summed_scores[base_word] / len(words)
        )

    return summed_scores


def _get_base_words(model, options):
    given_words = options.base_words.split(',')
    available_words = [word for word in given_words if word in model.wv.index_to_key]
    return available_words


def _get_meta_metadata(txt_file, options):
    txt_file = str(txt_file)
    if 'ocr.txt' in txt_file:
        # This converts something like `newspaper_dir/lccn/path/to/file` into
        # `lccn/path/to/file`. This simplifies accessing the metadata, even though
        # we need the original path to access the fulltext file.
        txt_path = txt_file.replace('ocr.txt', '').replace(options.newspaper_dir, '').lstrip('/')
        metadata_path = Path(options.metadata_dir) / txt_path
        idx = txt_path.split('/')[0]
    else:
        idx = txt_file.split('/')[-1]
        metadata_path = Path(options.metadata_dir) / idx

    return metadata_path, idx


def _init_score_ranges(base_words):
    ranges = {}

    # By setting min to the largest possible value, we guarantee it will be
    # overwritten by any smaller value we encounter.
    # The smallest possible value for min is actually -100, but we'll just
    # ignore anything that dissimilar -- the visualization will probably be more
    # readable if everything "dissimilar enough" is set to the baseline color.
    for base_word in base_words:
        ranges[base_word] = {'min': 100, 'max': 0}

    return ranges


def _update_score_ranges(score_ranges, scores):
    # If we encounter scores more extreme than anything we've aready
    # encountered, update our known score range accordingly.
    for key in scores.keys():
        score_ranges[key]['min'] = min(score_ranges[key]['min'], scores[key])
        score_ranges[key]['max'] = max(score_ranges[key]['max'], scores[key])

    return score_ranges


def update_metadata(model, options, iterator):
    base_words = _get_base_words(model, options)

    trivial_scores = { base_word: 0 for base_word in base_words }

    score_ranges = _init_score_ranges(base_words)
    for txt_file in iterator:
        output_path, idx = _get_meta_metadata(txt_file, options)

        if not output_path.is_file():
            logging.warning(f'Metadata file does not exist at {output_path}')
            continue

        logging.info(f'Updating metadata for {txt_file}...')

        try:
            scores = _derive_scores(model, txt_file, base_words)
        except ZeroDivisionError:
            # If len(words) = 0.
            scores = trivial_scores

        score_ranges = _update_score_ranges(score_ranges, scores)

        with output_path.open('r') as f:
            try:
                metadata = json.load(f)
            except json.decoder.JSONDecodeError:
                logging.exception(f'Malformed metadata; scores were {scores}')
                continue

        metadata[idx].update({SCORE_NAMESPACE: scores})

        with output_path.open('w') as f:
            json.dump(metadata, f)

    # This will help us evaluate whether documents vary enough on these words
    # to be interesting to visualize.
    logging.info(f'Score ranges: {score_ranges}')


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--model_path',
                        help='path to neural net used for computing similarities',
                        required=True)
    parser.add_argument('--base_words',
                        help='comma-separated list of words whose similarities will be computed',
                        required=True)
    parser.add_argument('--metadata_dir',
                        help='path to directory containing metadata files',
                        required=True)
    parser.add_argument('--newspaper_dir',
                        help='path to newspaper files')
    parser.add_argument('--results_dir',
                        help='path to non-newspaper files')
    parser.add_argument('--logfile', default="assign_similarity_metadata.log")

    return parser.parse_args()


if __name__ == '__main__':
    options = parse_args()

    initialize_logger(options.logfile)

    logging.info('Loading model...')
    try:
        model = gensim.models.Doc2Vec.load(options.model_path)
    except FileNotFoundError:
        logging.info('No model found')
        import sys; sys.exit()

    if options.newspaper_dir:
        logging.info('Processing newspapers...')
        update_metadata(model, options, Path(options.newspaper_dir).rglob('**/*.txt'))

    if options.results_dir:
        logging.info('Processing non-newspapers...')
        update_metadata(model, options, glob.iglob(f'{options.results_dir}/*'))
