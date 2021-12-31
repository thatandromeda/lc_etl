# New filter concept: Make sure everything in the document is actually a word!
#
# For each word in a document:
#   If it's a legitimate word, keep it
#   If it's not:
#     Find the words which are most similar in meaning, according to a
#     previously-trained neural net
#     Discard any below a minimum similarity threshold
#     See if any remaining have a small Levenshtein distance (i.e. could have
#     been produced by a handful of misrecognized characters in the OCR process)
#     If any options remain, substitute the most similar for the word in the
#     document
#     Otherwise, drop the word
#
# This has the following salutary properties:
# - eliminates gibberish
# - probably replaces words with the original in-document word
# - dramatically reduces the corpus vocabulary size, leading to much faster
#   neural net training (4x speedup during trials)
#
# Unfortunately, this takes almost literally forever.  Therefore this has a
# multiprocessing implementation, so that it can be parallelized.
#
# TODO: figure out how logs work with multiprocessing.
# time: cp -r old_results multithreaded_test; run this
# cp -r old_results multithreaded_test; run original

from argparse import ArgumentParser
import itertools
import logging
from math import floor
from multiprocessing import Pool, log_to_stderr
import os
from pathlib import Path
import sqlite3

import gensim
import Levenshtein
import more_itertools
import spacy

from .utilities import BASE_DIR
from .filter_newspaper_locations import normalize

GENSIM_THRESHOLD = 0.6
LEVENSHTEIN_THRESHOLD = .3

DB_DIR = 'nonword_caches'
DB_TABLE = 'words'
DB_NONWORD = 'nonword'
DB_GOOD_WORD = 'good_word'


def lookup_from_cache(db, word):
    query = db.execute(f"SELECT {DB_GOOD_WORD} FROM {DB_TABLE} WHERE {DB_NONWORD} = '{word}'")

    # We are assuming there is at most one match, based on how we're doing db
    # writes. (In a better world we'd verify this.)
    match = query.fetchone()

    if match:
        # Matches will be one-element tuples. We want only the string.
        return match[0]
    else:
        return None


def close_enough(base_word, test_word):
    # This will be 0 for words of 1 or 2 letters, but those are likely enough
    # to be garbage anyway that it's fine to let them fail here.
    allowable_distance = floor(LEVENSHTEIN_THRESHOLD * len(base_word))

    # Some errors look like single-character replacements; others look like word
    # fragmentation. Either is OK.
    return any([
        Levenshtein.distance(base_word, test_word) <= allowable_distance,
        base_word in test_word
    ])


def derive_from_model(model, nlp, base_word):
    """
    The goal here is to remove words that are probably OCR errors and replace
    them with a likely candidate. The hope here is that this will minimize the
    chances that artifacts specific to particular digitization workflows will
    artificially group together documents, rather than documents being grouped
    on the basis of their underlying contents. Doubtless it will sometimes
    (frequently?) introduce errors, but since it's only substituting words that
    are fairly similar in meaning, that should only moderately affect downstream
    clustering.

    The threshold of 0.6 was chosen by looking at various real-world OCR errors
    and seeing their similarities to the correct word (typically .65-.75). The
    Levenshtein threshold, similarly.
    """
    try:
        options = model.wv.most_similar(base_word)
    except Exception as e:
        return None

    similar_words = [opt[0] for opt in options if opt[1] > GENSIM_THRESHOLD]

    # This has a side effect that a number of slurs which are common in the
    # corpus are not in fact part of the NLP corpus here and will be filtered
    # out. That's clearly a good thing mental-health-wise for me as someone
    # viewing many examples of this function at work. Whether or not it's a
    # good thing for accuracy of corpus handling or downstream uses is left as
    # an exercise for the reader.
    real_words = [word for word in similar_words if word in nlp.vocab.strings]
    close_words = [word for word in real_words if close_enough(base_word, word)]

    # As the model returned these in order by similarity, with most-similar
    # first, and as our list transformations have been order-preserving, the
    # first word in the list is still the most similar of the surviving options,
    # so let's go with it.
    try:
        return close_words[0]
    except IndexError:
        return None


def check_for_alternative(db, model, nlp, base_word):
    cached_word = lookup_from_cache(db, base_word)

    if cached_word:
        return cached_word
    else:
        result = derive_from_model(model, nlp, base_word)

        # If we're in this branch of the if statement, this result had not yet
        # been cached, so let's cache it.
        if result:
            # The quote types are important here! If you use single quotes
            # around the values, the parse will break when the values include
            # single quotes/apostrophes (such as the word "don't".)
            db.execute(f'INSERT INTO {DB_TABLE} VALUES ("{base_word}", "{result}")')
            db.commit()

        return result


def get_cache(model_path):
    # sqlite3 will not create the directory structure if it doesn't exist, so
    # we need to make sure to do that.
    db_path = Path(BASE_DIR, DB_DIR)
    db_path.mkdir(parents=True, exist_ok=True)
    filename = Path(model_path).with_suffix('.db').name
    db_name = db_path / filename

    if db_name.is_file():
        db = sqlite3.connect(db_name)
    else:
        db = sqlite3.connect(db_name)
        db.execute(f"CREATE TABLE {DB_TABLE} ({DB_NONWORD}, {DB_GOOD_WORD})")
        db.commit()

    return db


def _inner_filter(iterable, db, model, nlp):
    for txt_file in iterable:
        with open(txt_file, 'r') as f:
            text = f.read()

        new_text = []

        for word in text.split():
            word = normalize(word)
            # Keep things that are actually words. This includes proper nouns
            # such as place names.
            if word in nlp.vocab.strings:
                new_text.append(word)
            else:
                alt_word = check_for_alternative(db, model, nlp, word)
                if alt_word:
                    new_text.append(alt_word)

        filtered_text = ' '.join(new_text)

        with open(txt_file, 'w') as f:
            f.write(filtered_text)


def manage_filter(iterable, model_path):
    """
    This sets up the infrastructure we'll need for filtering, but delegates the
    actual filtering to _inner_filter. This lets us ensure we've closed the db
    without making things too hard to read.
    We need to do this inside of manage_filter because Pool processes can't
    share data structures; they have to pickle data and send it across at an OS
    level. However, the model and the db connection aren't picklable. Therefore
    each process needs its own. This unfortunately increases overall memory
    usage (carrying around n separate instances of the model isn't cheap), but
    makes time-to-completion radically shorter.
    """

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logging.info('The spaCy corpus is not available. `python -m spacy download en_core_web_sm` and try again.')
        import sys; sys.exit()

    try:
        model = gensim.models.Doc2Vec.load(model_path)
    except AttributeError:
        logging.exception('No model provided; cannot continue')
        import sys; sys.exit()

    db = get_cache(model_path)

    try:
        # I'd sure like to set this up using multiprocessing, but these
        # arguments are not all picklable, and then we're sad.
        _inner_filter(iterable, db, model, nlp)
    finally:
        db.close()


def num_processes(options):
    # Default to using half of the processors if the users didn't specify.
    desired_num = int(options.p) or floor(os.cpu_count()/2)
    # Don't let the user exceed the cpu count.
    return min(desired_num, os.cpu_count())


def _filter(options):
    all_files_iterable = Path(options.target_dir).rglob('*.txt')

    num = num_processes(options)

    with Pool(processes=num) as pool:
        subset_iterables = more_itertools.divide(num, all_files_iterable)
        # The zip lets us supply 2 arguments to the manage_filter function.
        # The first will be one of the subset_iterables (distinct for each
        # process); the second will always be options.model_path.
        pool.starmap(
            manage_filter,
            zip(subset_iterables, itertools.repeat(options.model_path))
        )



if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--target_dir', help='directory containing files to check', required=True)
    parser.add_argument('--model_path', help='path to neural net to use for word similarity', required=True)
    parser.add_argument('--p', help='processes to run (max is os.cpu_count() regardless of this value)')
    parser.add_argument('--logfile', default="filter_nonwords_<id>.log")
    options = parser.parse_args()

    _filter(options)

# for `canton`, 2-letter changes are common (e.g. 'cautou')
# >>> model.wv.most_similar('cautou')
# [('mis3', 0.6734908819198608), ('canton', 0.6474270224571228), ('jacksox',
# 0.6214158535003662), ('3m', 0.6087878942489624), ('cantox', 0.599487841129303),
# ('jackson', 0.5969511866569519), ('offick', 0.5901390910148621), ('6m',
# 0.5873024463653564), ('v7', 0.5811986923217773), ('osyka', 0.5809045433998108)]

# >>> model.wv.most_similar('frage')
# [('suffrage', 0.6635172367095947), ('baldness', 0.5722435712814331), ('fere',
# 0.5628131628036499), ('fering', 0.5568088293075562), ('rights',
# 0.5475192666053772), ('aggression', 0.5430271625518799), ('fered',
# 0.5414115786552429), ('citizenship', 0.5353204607963562), ('disa',
# 0.5345199108123779), ('inflicted', 0.5147979259490967)]
