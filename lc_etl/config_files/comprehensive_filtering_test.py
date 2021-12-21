import string

from gensim.parsing.preprocessing import remove_stopwords

IDENTIFIER = 'comprehensive_filtering'

NEWSPAPER_DIR = 'newspapers_full_filtering_pipeline_test'

RESULTS_DIR = 'results_full_filtering_pipeline_test'

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
