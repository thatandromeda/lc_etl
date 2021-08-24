from argparse import ArgumentParser
import logging
import os
import pickle
import sys
import time

from gensim.models.doc2vec import Doc2Vec
from gensim.models.callbacks import CallbackAny2Vec

from queries import slurp

import logging

parser = ArgumentParser()
parser.add_argument('--load', help='filename of pickled corpus to load')
options = parser.parse_args()

timestamp = time.strftime('%Y%m%d_%H%M%S', time.localtime())
logging.basicConfig(filename=f'{output_dir}/train_{timestamp}.log',
                    format="%(asctime)s:%(levelname)s:%(message)s",
                    level=logging.INFO)

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

def build_corpus():
    corpus = []
    for document in slurp(as_iterator=True):
        if not document[1]:     # don't process empty documents
            continue

        corpus.append(read_document(document))

        # I keep getting timeout errors. Let's checkpoint this.
        if len(corpus) % 20 == 0:
            with open(f'{output_dir}/corpus_{timestamp}_{len(corpus)}.pkl', 'wb') as f:
                pickle.dump(corpus, f)

            prev_checkpoint = f'{output_dir}/corpus_{timestamp}_{len(corpus) - 20}.pkl'
            if os.path.exists(prev_checkpoint):
                os.remove(prev_checkpoint)

    return corpus

loadfile = options.load
if loadfile:
    corpus = pickle.load(open(loadfile, 'rb'))
else:
    corpus = build_corpus()
    with open(f'{output_dir}/corpus_{timestamp}.pkl', 'wb') as f:
        pickle.dump(corpus, f)

model = Doc2Vec(vector_size=50, min_count=2, epochs=40)
model.build_vocab(corpus)
model.train(corpus,
            total_examples=model.corpus_count,
            epochs=model.epochs,
            callbacks=[epoch_logger])
model.save(f'{output_dir}/model_{timestamp}')
# load with model = gensim.models.Doc2Vec.load("path/to/model")
