import string

from gensim.parsing.preprocessing import remove_stopwords

IDENTIFIER = 'nonwords_replaced'

NEWSPAPER_DIR = 'filtered_newspapers'

NEWSPAPER_DIR_REGEX = '\/1877\/'

RESULTS_DIR = 'filtered_results'

MIN_FREQUENCY = 30

EPOCHS = 100

MODEL_OPTIONS = {
    'vector_size': 100,
    'alpha': 0.1,
    'window': 8,
    'sample': 0.00001,
    'workers': 8
}

VOCABULARY = f'{IDENTIFIER}.dict'

def filter_stopwords(text):
    return remove_stopwords(text)
