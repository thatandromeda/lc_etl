import string

from gensim.parsing.preprocessing import remove_stopwords

IDENTIFIER = 'test_🎉'

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
    'workers': 6
}

VOCABULARY = f'{IDENTIFIER}.dict'

def filter_stopwords(text):
    return remove_stopwords(text)


def tokenize(text):
    text = text.translate(text.maketrans('', '', string.punctuation))
    return text.lower().split()
