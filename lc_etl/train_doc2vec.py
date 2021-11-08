from argparse import ArgumentParser
from collections import defaultdict
import logging
import glob
import re
import time

from gensim import corpora
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.models.callbacks import CallbackAny2Vec
from gensim.parsing.preprocessing import remove_stopwords

from .utilities import make_timestamp, initialize_logger

output_dir = 'gensim_outputs'
timestamp = make_timestamp()

NEWSPAPER_DIR_DEFAULT = 'newspapers'

# TODO
# definitely want some kind of stemming, to deal with things like acre/acres,
# which are otherwise quite similar
# also you're going to need to remove punctuation (not hyphens, which are
# useful, but definitely commas, probably more)
# a pass for multiword tokens, somehow??
# introspect dictionary to see a good min-frequency setting by looking at
# frequency of OCR misspellings. I might actually want a version trained on
# these to use as an OCR-Levenshtein type source!-- it's useful for the search,
# when I get to that, as a search for cotton should absolutely find things like
# "cottou". But it is maybe not so useful for grouping documents.

# Words must appear at least this often in the corpus to be used in training.
MIN_FREQUENCY = 5

class EpochLogger(CallbackAny2Vec):
    def __init__(self):
        self.epoch = 0
        self.time = time.time()

    def on_epoch_begin(self, model):
        self.time = time.time()
        logging.info("Epoch #{} start".format(self.epoch))

    def on_epoch_end(self, model):
        seconds = round(time.time() - self.time, 1)
        # Loss in Doc2Vec is actually super dodgy -- not sure what
        # get_latest_training_loss reports -- but it's in the API.
        # https://github.com/RaRe-Technologies/gensim/issues/2983
        logging.info(f'Epoch {self.epoch} trained in {seconds} seconds')
        logging.info(f'Loss after epoch {self.epoch}: {model.get_latest_training_loss()}')
        self.epoch += 1

epoch_logger = EpochLogger()


# Iterates through all available LoC files, yielding (document, tag).
# Document is unprocessed -- a straight read of the file.
class LocDiskIterator:
    def __init__(self, newspaper_dir):
        super(LocDiskIterator, self).__init__()
        self.newspaper_dir = newspaper_dir
        self.newspaper_path = re.compile(f'{self.newspaper_dir}/([\w/-]+)/ocr.txt')

    def __iter__(self):
        # First do newspapers
        for newspaper in glob.iglob(f'{self.newspaper_dir}/**/*.txt', recursive=True):
            # Expected path format: 'newspapers/lccn/yyyy/mm/dd/ed-x/seq-x/ocr.txt'
            tag = self.newspaper_path.match(newspaper).group(1)
            with open(newspaper, 'r') as f:
                document = f.read()

            yield (document, tag)

        # Then do everything else
        for result in glob.iglob('results/*'):
            # Expected path: 'results/lccn'
            tag = result.split('/')[-1]
            with open(result, 'r') as f:
                document = f.read()

            yield (document, tag)


# Iterates through all available LoC files, yielding TaggedDocuments.
class LocCorpus:
    def __init__(self, newspaper_dir):
        self.newspaper_dir = newspaper_dir

    def __iter__(self):
        for document, tag in LocDiskIterator(self.newspaper_dir):
            yield TaggedDocument(preprocess(document), [tag])


# Most basic possible stopword filtering. It's encapsulated into a function
# to make it easy to swap out later.
def filter_stopwords(text):
    return remove_stopwords(text)


# Most basic possible tokenizing. It's encapsulated into a function
# to make it easy to swap out later.
# Make sure to split on any whitespace, not just spaces! This is the
# default behavior of split.
def tokenize(text):
    return text.lower().split()


# Encapsulate all our preprocessing steps, so we can easily swap out the whole
# pipeline.
def preprocess(text):
    text = filter_stopwords(text)
    text = tokenize(text)
    return text


def make_dictionary():
    frequency = defaultdict(int)
    for text, _ in LocDiskIterator():
        text = preprocess(text)
        for token in text:
            frequency[token] += 1

    # This will have millions of items. Hopefully that's cool.
    filtered_freq = {k: v for k, v in frequency.items() if v > MIN_FREQUENCY }
    dictionary = corpora.Dictionary(filtered_freq)
    dictionary.save('loc_{timestamp}.dict')

    return dictionary


def read_document(document, tokens_only=False):
    doc_id, text = document
    tokens = gensim.utils.simple_preprocess(text)

    if tokens_only:
        return tokens
    else:
        # For training data, add tags
        return gensim.models.doc2vec.TaggedDocument(tokens, [doc_id])

# train_corpus = list(read_document(lee_train_file))
# test_corpus = list(read_document(lee_test_file, tokens_only=True))

# Although I will run this from the command line, I need things to be importable
# into the shell for debugging.
if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--newspaper_dir',
                        help='directory containing newspaper files',
                        default=NEWSPAPER_DIR_DEFAULT)
    parser.add_argument('--logfile',
                        help='name of log file',
                        default=f'{output_dir}/train_{timestamp}.log')
    options = parser.parse_args()

    initialize_logger(options.logfile)

    model = Doc2Vec(vector_size=50, min_count=2, epochs=40)
    model.build_vocab(LocCorpus(options.newspaper_dir))
    # Must re-initialize the corpus so that the iterator hasn't run off the end of
    # it!
    model.train(LocCorpus(options.newspaper_dir),
                total_examples=model.corpus_count,
                epochs=model.epochs,
                callbacks=[epoch_logger])
    model.save(f'{output_dir}/model_{timestamp}')
    # load with model = gensim.models.Doc2Vec.load("path/to/model")
