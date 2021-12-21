IDENTIFIER = 'everything'

NEWSPAPER_DIR = 'newspapers_everything'

RESULTS_DIR = 'results_everything'

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
