from collections import defaultdict
import logging
import glob
import re
import time

from gensim import corpora
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.models.callbacks import CallbackAny2Vec
from gensim.parsing.preprocessing import remove_stopwords

import logging

output_dir = 'gensim_output'
timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
logging.basicConfig(filename=f'{output_dir}/train_{timestamp}.log',
                    format="%(asctime)s:%(levelname)s:%(message)s",
                    level=logging.INFO)

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
        # It would be great to display the loss here, but loss isn't actually
        # implemented on Doc2Vec:
        # https://github.com/RaRe-Technologies/gensim/issues/2983
        logging.info(f'Epoch {self.epoch} trained in {seconds} seconds')
        logging.info(f'Loss after epoch {self.epoch}: {loss}')
        self.epoch += 1

epoch_logger = EpochLogger()


# Iterates through all available LoC files, yielding (document, tag).
# Document is unprocessed -- a straight read of the file.
class LocDiskIterator:
    def __init__(self):
        super(LocDiskIterator, self).__init__()
        self.newspaper_path = re.compile('newspapers/([\w/-]+)/ocr.txt')

    def __iter__(self):
        # First do newspapers
        for newspaper in glob.iglob('newspapers/**/*.txt', recursive=True):
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
    def __iter__(self):
        for document, tag in LocDiskIterator():
            yield TaggedDocument(preprocess(document), [tag])


# Most basic possible stopword filtering. It's encapsulated into a function
# to make it easy to swap out later.
def filter_stopwords(text):
    return remove_stopwords(text)


# Most basic possible tokenizing. It's encapsulated into a function
# to make it easy to swap out later.
def tokenize(text):
    return text.lower().split(' ')


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

corpus = LocCorpus()
model = Doc2Vec(vector_size=50, min_count=2, epochs=40)
model.build_vocab(corpus)
model.train(corpus,
            total_examples=model.corpus_count,
            epochs=model.epochs,
            callbacks=[epoch_logger])
model.save(f'{output_dir}/model_{timestamp}')
# load with model = gensim.models.Doc2Vec.load("path/to/model")
