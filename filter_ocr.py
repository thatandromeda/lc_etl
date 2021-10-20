from argparse import ArgumentParser
from pathlib import Path

DICT_SOURCE = '/usr/share/dict/words'
THRESHOLD = 0.625

parser = ArgumentParser()
parser.add_argument('--target_dir', help='directory containing files to check')
parser.add_argument('--dict_source', help='path to dictionary file',
                    default=DICT_SOURCE)
parser.add_argument('--threshold',
                    help='minimum fraction of acceptable words (between 0 and 1)',
                    default=THRESHOLD)
options = parser.parse_args()

def filter_for_quality(target_dir, dict_source=DICT_SOURCE, threshold=THRESHOLD):
    """
    Find all .txt files in the target directory; check to see if they have
    adequate OCR quality; and delete any which do not.
    """
    good_files = 0
    total_files = 0

    with Path(dict_source).open() as f:
        dictionary = f.read().splitlines()

    for txt_file in Path(target_dir).rglob('*.txt'):
        total_files += 1
        if total_files % 100 == 0:
            print(f'{total_files} checked')
        good_words = 0

        with txt_file.open() as f:
            text = f.read()
        tokens = text.split(' ')

        total_words = len(tokens)
        if not total_words:
            # Delete empty files.
            Path(txt_file).unlink()
            continue

        # Set intersection with the dictionary is tempting here, but don't;
        # that would count every occurrence of (for example) "the" as a single
        # word, which would make it impossible to tell what percent were
        # properly OCRed.
        for token in tokens:
            if token in dictionary:
                good_words += 1

        if good_words / total_words < threshold:
            Path(txt_file).unlink()
        else:
            good_files += 1

    try:
        print(f'{good_files} good files found of {total_files} total files ({round(100*good_files/total_files)} percent)')
    except ZeroDivisionError:
        print('No files found.')


if __name__ == '__main__':
    filter_for_quality(options.target_dir, options.dict_source, options.threshold)
