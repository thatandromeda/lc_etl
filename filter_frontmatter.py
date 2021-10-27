from argparse import ArgumentParser
from pathlib import Path

# This cutoff was determined by:
# - looking at a random sample of 100 files
#   (`find filtered_newspapers/ -name \*.txt | shuf -n 50`, taken twice)
# - removing any whose OCR was unreadable (the filtering process was not yet
#   done at this point, so some of the files in filtered_newspapers were not
#   well-OCRed)
# - counting the number of lines in each file dedicated to repetitive front
#   matter (newspaper name, publisher, city of publication, date, ad rates)
# - looking at the mean, median, 75th percentile, and 90th percentile.
#
# The mean and 75th percentile were both 4, because the vast majority of
# newspaper pages have only a handful of lines of front matter. A few, which
# publish lengthy ad rates, have many more (35+). Taking the 90th percentile
# removes front matter from nearly all newspapers without removing a signficant
# amount of content. Papers which lead with their ad rates will still likely
# end up grouped together on that basis.
CUTOFF = 7

parser = ArgumentParser()
parser.add_argument('--target_dir', help='directory containing files to check')
parser.add_argument('--cutoff',
                    help='number of lines to remove from the front matter',
                    default=CUTOFF)
options = parser.parse_args()

def filter_frontmatter(target_dir, cutoff=CUTOFF):
    """
    Find all .txt files in the target directory; remove $cutoff lines from the
    front.
    """
    total_files = 0

    for txt_file in Path(target_dir).rglob('*.txt'):
        total_files += 1
        if total_files % 100 == 0:
            print(f'{total_files} edited')

        with txt_file.open() as f:
            text = f.readlines()

        shorter_text = text[CUTOFF:]

        if shorter_text:
            with txt_file.open('w') as f:
                f.write(' '.join(shorter_text))
        else:
            Path(txt_file).unlink()


if __name__ == '__main__':
    filter_frontmatter(options.target_dir, options.cutoff)
