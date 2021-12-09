# The original strategy used to see if texts mostly contain accurately OCRed
# words was to loop through the first thousand words of each text to see if
# they were in /usr/share/dict/words. This has two disadvantages:
# 1) /usr/share/dict/words does not know about morphological variants, like
#   "bravest";
# 2) it's incredibly slow.
#
# This filter takes the alternate strategies of:
# 1) using spacy's en_core_web_sm corpus, which does know about inflected forms;
# 2) looking at the set intersection of that corpus with a document subset.
#
# This is dramatically faster (almost 10x, benchmarking against a subset of the
# newspaper corpus).
#
# It is also somewhat less accurate. Because sets don't allow for duplicate
# members, they can't represent the word distributions in the underlying
# document. Every token is equally important, so a legitimate word that occurs
# dozens of times has the same impact as a bad word that occurs only once (or
# vice versa).
#
# However, by adjusting the parameters (amount of text examined, length of
# tokens considered, cutoff score), I can end up filtering down to a set of
# documents that is pretty similar to the set I got with my original, more
# scrupulous filter. For a nearly 10x speedup this is worth it, considering
# that the original filter was taking me literally days to run on a million-
# document corpus.
#
# I also considered throwing Bayesian statistics at the process, to iterate
# through words only until I had seen enough to be reasonably confident that
# the document was above (or below) my quality threshold. In theory, this would
# have been faster without a significant accuracy tradeoff. However, 1) this was
# only about 10% faster than the original approach, and 2) I was not at all
# confident that I was doing the statistics right.

from argparse import ArgumentParser
from pathlib import Path
import logging

import spacy

from train_doc2vec import Configuration
from utilities import initialize_logger

def filter_for_quality(target_dir):
    """
    Find all .txt files in the target directory; check to see if they have
    adequate OCR quality; and delete any which do not. Use a probabilistic
    measure to determine whether we have checked enough words per file.
    """
    cutoff = 0.57
    words_to_examine = 400
    min_word_length = 3

    total_files = 0
    good_files = 0

    dictionary = set(spacy.load("en_core_web_sm").vocab.strings)

    for txt_file in Path(target_dir).rglob('*.txt'):

        with txt_file.open() as f:
            text = f.read()

        # Use same tokenization behavior that the training process will use by
        # default.
        tokens = set([
            word for word in Configuration.tokenize(text)[:words_to_examine]
            if len(word) > min_word_length
        ])
        if not len(tokens):
            print(f'{txt_file} has no long tokens and is bad')
            continue

        total_files += 1

        if total_files % 100 == 0:
            logging.info(f'{total_files} processed, {good_files} good files found ({round(100*good_files/total_files, 1)}%)')

        good_tokens = dictionary.intersection(tokens)
        estimator = len(good_tokens) / len(tokens)

        if estimator < cutoff:
            try:
                Path(txt_file).unlink()
            except FileNotFoundError:
                # File may have already been deleted if multiple filters are
                # running in parallel.
                continue
        else:
            good_files += 1

    try:
        logging.info(f'{good_files} good files found of {total_files} total files ({round(100*good_files/total_files)} percent)')
    except ZeroDivisionError:
        logging.info('No files found.')

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--target_dir', help='directory containing files to check')
    parser.add_argument('--logfile', default="filter_ocr.log")
    options = parser.parse_args()

    initialize_logger(options.logfile)

    filter_for_quality(options.target_dir)
