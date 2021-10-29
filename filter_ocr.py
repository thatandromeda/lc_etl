from argparse import ArgumentParser
from pathlib import Path

from train_doc2vec import tokenize

DICT_SOURCE = '/usr/share/dict/words'
THRESHOLD = 0.625
LOGFILE = 'ratings.txt'

def filter_for_quality(target_dir, dict_source=DICT_SOURCE, threshold=THRESHOLD):
    """
    Find all .txt files in the target directory; check to see if they have
    adequate OCR quality; and delete any which do not.
    """
    good_files = 0
    total_files = 0
    num_to_check = 1000

    with Path(dict_source).open() as f:
        dictionary = f.read().splitlines()
        dictionary = [word.lower() for word in dictionary]

    for txt_file in Path(target_dir).rglob('*.txt'):
        total_files += 1
        if total_files % 100 == 0:
            print(f'{good_files} good files found of {total_files} total files ({round(100*good_files/total_files)} percent)')

        with txt_file.open() as f:
            text = f.read()

        # Use same tokenization behavior that the training process will use.
        tokens = tokenize(text)

        # Set intersection with the dictionary is tempting here, but don't;
        # that would count every occurrence of (for example) "the" as a single
        # word, which would make it impossible to tell what percent were
        # properly OCRed.
        # Also, we won't bother processing the entire file; if the quality is
        # terrible, it will be obvious soon enough. ChronAm files range from 1
        # word to >20K, with the vast majority of them well over 1000, so this
        # will result in a substantial time savings.
        good_words = 0
        for token in tokens[:num_to_check]:
            if token in dictionary:
                good_words += 1

        rating = good_words / min(len(tokens), num_to_check)
        with Path(LOGFILE).open('a') as f:
            f.write(str(rating))

        if rating < threshold:
            Path(txt_file).unlink()
        else:
            good_files += 1

    try:
        print(f'{good_files} good files found of {total_files} total files ({round(100*good_files/total_files)} percent)')
    except ZeroDivisionError:
        print('No files found.')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--target_dir', help='directory containing files to check')
    parser.add_argument('--dict_source', help='path to dictionary file',
                        default=DICT_SOURCE)
    parser.add_argument('--threshold',
                        help='minimum fraction of acceptable words (between 0 and 1)',
                        default=THRESHOLD)
    options = parser.parse_args()

    filter_for_quality(options.target_dir, options.dict_source, options.threshold)
