from argparse import ArgumentParser
from collections import defaultdict
import glob
from importlib import import_module
import logging
from pathlib import Path
import re
import string
import time

from gensim import corpora
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.models.callbacks import CallbackAny2Vec
from gensim.parsing.preprocessing import remove_stopwords

from utilities import make_timestamp, initialize_logger, BASE_DIR

output_dir = f'{BASE_DIR}/gensim_outputs'

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

class EpochLogger(CallbackAny2Vec):
    def __init__(self):
        self.epoch = 1  # I think this is 1-indexed (!)
        self.time = time.time()

    def on_epoch_begin(self, model):
        self.time = time.time()
        logging.info("Epoch #{} start".format(self.epoch))

    def on_epoch_end(self, model):
        seconds = round(time.time() - self.time, 1)
        # It would be great to report loss here, but loss in Doc2Vec is actually
        # super dodgy. It's in the API --
        # https://github.com/RaRe-Technologies/gensim/issues/2983 --
        # but always reports as 0.
        logging.info(f'Epoch {self.epoch} trained in {seconds} seconds')
        self.epoch += 1


# Iterates through all available LoC files, yielding (document, tag).
# Document is unprocessed -- a straight read of the file.
class LocDiskIterator:
    def __init__(self, config):
        super(LocDiskIterator, self).__init__()
        self.newspaper_dir = config.newspaper_dir
        self.newspaper_dir_regex = config.newspaper_dir_regex
        self.results_dir = config.results_dir
        self.newspaper_path = re.compile(f'{self.newspaper_dir}/([\w/-]+)/ocr.txt')

    def __iter__(self):
        # First do newspapers
        for newspaper in glob.iglob(f'{self.newspaper_dir}/**/*.txt', recursive=True):
            # Expected path format: 'newspapers/lccn/yyyy/mm/dd/ed-x/seq-x/ocr.txt'

            # We can't use regular expressions in glob, so we'll perform some
            # post hoc filtering to skip anything that doesn't match our
            # desired path.
            if not re.search(self.newspaper_path, newspaper):
                continue

            tag = self.newspaper_path.search(newspaper).group(1)
            with open(newspaper, 'r') as f:
                document = f.read()

            yield (document, tag)

        # Then do everything else
        for result in glob.iglob(f'{self.results_dir}/*'):
            # Expected path: 'results/lccn'
            tag = result.split('/')[-1]
            with open(result, 'r') as f:
                document = f.read()

            yield (document, tag)


# Iterates through all available LoC files, yielding TaggedDocuments.
class LocCorpus:
    def __init__(self, config):
        self.config = config

    def __iter__(self):
        for document, tag in LocDiskIterator(self.config):
            yield TaggedDocument(preprocess(config, document), [tag])


class Configuration(object):
    """Holds config options for this training run. It reads them from a config
    file provided on the command line and supplies defaults as needed.

    Args:
        config_file (str)
            Relative path to the file containing configuration values, e.g.
            `config_files.example`

    Values which may be defined in the configuration file (all optional):
        IDENTIFIER (str):
            Will be used in dictionary and model file names.

        NEWSPAPER_DIR (str):
            The directory in which to look for newspaper files, relative to the
            project BASE_DIR. Useful if you have maintained an original
            directory and used a particular directory for postprocessed
            versions.
            This must be a _string_, suitable for shell expansion, not a regex.

        NEWSPAPER_DIR_REGEX (str):
            If you need to filter only for paths matching a particular regex,
            do that here. This is used ONLY for filtering newspaper directories,
            NOT for specifying where to look.

        RESULTS_DIR (str):
            The directory in which to look for non-newspaper files, relative to
            the project BASE_DIR.

        MIN_FREQUENCY (int):
            How often a word must appear in the corpus to be used in the neural
            net.

        EPOCHS (int):
            Number of epochs to use in model training.

        filter_stopwords (function)

        tokenize (function)

        training_options (function):
            Takes arg `model` (a Doc2Vec model). Its output, a dict, will be
            supplied to `model.train`; consult gensim documentation for
            parameters.

        model_options (dict):
            Will be used to initialize the Doc2Vec model.

        vocabulary (str):
            Load a vocabulary from a saved dict by this name. If no dict with
            this name is found, a vocabulary will be built from scratch.
    """

    # Words must appear at least this often in the corpus to be used in
    # training, unless overridden by the config file.
    MIN_FREQUENCY = 25

    EPOCHS = 40

    MODEL_DEFAULTS = {
        'vector_size': 50, 'min_count': MIN_FREQUENCY, 'epochs': EPOCHS
    }

    def __init__(self, config_file):
        super(Configuration, self).__init__()
        self.config_file = import_module(config_file)
        self.timestamp = make_timestamp()
        self.identifier = self._get_identifier()
        self.newspaper_dir = self._get_newspaper_dir()
        self.newspaper_dir_regex = self._get_newspaper_dir_regex()
        self.results_dir = self._get_results_dir()
        self.min_frequency = self._get_min_frequency()
        self.filter_stopwords = self._get_filter_stopwords()
        self.tokenize = self._get_tokenize()
        self.model_options = self._get_model_options()
        self.vocabulary = self.config_file.VOCABULARY


    def _get_identifier(self):
        try:
            return f'{self.config_file.IDENTIFIER}_{self.timestamp}'
        except AttributeError:
            return f'defaults_{self.timestamp}'


    def _get_newspaper_dir(self):
        try:
            return Path(f'{BASE_DIR}') / f'{self.config_file.NEWSPAPER_DIR}'
        except AttributeError:
            return Path(f'{BASE_DIR}') / 'filtered_newspapers'


    def _get_newspaper_dir_regex(self):
        try:
            regex = self.config_file.NEWSPAPER_DIR_REGEX
            return regex.rstrip('/')
        # If no regex was specified, return one that matches everything (except
        # newlines).
        except AttributeError:
            return '.*'


    def _get_results_dir(self):
        try:
            return Path(f'{BASE_DIR}') / f'{self.config_file.RESULTS_DIR}'
        except AttributeError:
            return Path(f'{BASE_DIR}') / 'results'


    def _get_min_frequency(self):
        try:
            return self.config_file.MIN_FREQUENCY
        except AttributeError:
            return self.MIN_FREQUENCY


    def _get_min_frequency(self):
        try:
            return self.config_file.EPOCHS
        except AttributeError:
            return self.EPOCHS


    def _get_filter_stopwords(self):
        try:
            return self.config_file.filter_stopwords
        except AttributeError:
            return self.filter_stopwords


    def _get_tokenize(self):
        try:
            return self.config_file.tokenize
        except AttributeError:
            return self.tokenize


    def training_options(self, model):
        training_defaults = {
            'total_examples': model.corpus_count,
            'epochs': model.epochs,
            'word_count': 0,
            'callbacks': [EpochLogger()]
        }

        try:
            updates = self.config_file.training_options(model)
        except AttributeError:
            updates = {}

        return {**training_defaults, **updates}


    def _get_model_options(self):
        try:
            updates = self.config_file.model_options()
        except AttributeError:
            updates = {}

        return {**self.MODEL_DEFAULTS, **updates}

    # Most basic possible stopword filtering. It's encapsulated into a function
    # to make it easy to swap out later.'
    @classmethod
    def filter_stopwords(cls, text):
        return remove_stopwords(text)


    # Most basic possible tokenizing. It's encapsulated into a function
    # to make it easy to swap out later.
    # Make sure to split on any whitespace, not just spaces! This is the
    # default behavior of split.
    @classmethod
    def tokenize(cls, text):
        text = text.translate(text.maketrans('', '', string.punctuation))
        return text.lower().split()


# Encapsulate all our preprocessing steps, so we can easily swap out the whole
# pipeline.
def preprocess(config, text):
    text = config.filter_stopwords(text)
    text = config.tokenize(text)
    return text


def dictionary_name_for(config):
    return config.vocabulary


def make_dictionary(config):
    frequency = defaultdict(int)
    for text, _ in LocDiskIterator(config):
        text = preprocess(config, text)
        for token in text:
            frequency[token] += 1

    # This will have millions of items. Hopefully that's cool.
    filtered_freq = {k: v for k, v in frequency.items() if v > MIN_FREQUENCY }
    dictionary = corpora.Dictionary(filtered_freq)
    dictionary.save(dictionary_name_for(config))

    return dictionary


def read_document(document, tokens_only=False):
    doc_id, text = document
    tokens = gensim.utils.simple_preprocess(text)

    if tokens_only:
        return tokens
    else:
        # For training data, add tags
        return gensim.models.doc2vec.TaggedDocument(tokens, [doc_id])


def initialize_vocabulary(config, model):
    try:
        corpus = corpora.Dictionary.load(dictionary_name_for(config))
        model.build_vocab_from_freq(corpus)
    # FileNotFoundError will be thrown for an invalid filename; AttributeError
    # will be thrown if the filename is None (i.e. not defined in the config
    # file). Either way we'll need to build the vocab from scratch.
    except (FileNotFoundError, AttributeError):
        model.build_vocab(LocCorpus(config))


# train_corpus = list(read_document(lee_train_file))
# test_corpus = list(read_document(lee_test_file, tokens_only=True))

# Although I will run this from the command line, I need things to be importable
# into the shell for debugging.
if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--config_file',
                        help='import_path.to.configuration_file, suitable for `import`',
                        default=None)
    # This is separate from the config file because the same logfile may be
    # passed to every script along the pipeline, whereas the config file holds
    # information unique to this script.
    parser.add_argument('--logfile', default="train_doc2vec.log")
    options = parser.parse_args()
    config = Configuration(options.config_file)

    initialize_logger(options.logfile or f'{config.identifier}.log')

    logging.info('Defining model')
    model = Doc2Vec(**config.model_options)

    logging.info('Building model vocabulary')
    initialize_vocabulary(config, model)

    # Must re-initialize the corpus so that the iterator hasn't run off the end of
    # it!
    logging.info('Training model')
    model.train(LocCorpus(config), **config.training_options(model))

    logging.info('Saving model')
    model.save(f'{output_dir}/model_{config.identifier}')
    # load with model = gensim.models.Doc2Vec.load("path/to/model")
