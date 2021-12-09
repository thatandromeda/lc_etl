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
# It will probably take almost literally forever to run.

from argparse import ArgumentParser
import logging
from math import floor
from pathlib import Path

import gensim
import Levenshtein
import spacy

from utilities import initialize_logger
from filter_newspaper_locations import normalize

GENSIM_THRESHOLD = 0.6
LEVENSHTEIN_THRESHOLD = .3


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


def check_for_alternative(model, nlp, base_word):
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


def filter(target_dir, model_path):
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logging.info('The spaCy corpus is not available. `python -m spacy download en_core_web_sm` and try again.')
        import sys; sys.exit()

    model = gensim.models.Doc2Vec.load(model_path)

    files_checked = 0

    for txt_file in Path(target_dir).rglob('*.txt'):
        with open(txt_file, 'r') as f:
            text = f.read()

        new_text = []

        logging.info(f'Replacing nonwords in {txt_file}')

        for word in text.split():
            word = normalize(word)
            # Keep things that are actually words. This includes proper nouns
            # such as place names.
            if word in nlp.vocab.strings:
                new_text.append(word)
            else:
                alt_word = check_for_alternative(model, nlp, word)
                if alt_word:
                    new_text.append(alt_word)

        filtered_text = ' '.join(new_text)

        with open(txt_file, 'w') as f:
            f.write(filtered_text)

        files_checked += 1
        if files_checked % 100 == 0:
            logging.info(f'{files_checked} files edited')

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--target_dir', help='directory containing files to check')
    parser.add_argument('--model_path', help='path to neural net to use for word similarity')
    parser.add_argument('--logfile', default="filter_frontmatter.log")
    options = parser.parse_args()

    initialize_logger(options.logfile)

    filter(options.target_dir, options.model_path)

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
