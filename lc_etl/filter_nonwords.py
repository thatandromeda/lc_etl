# New filter concept: make it just have words!
# for each word in a document:
#   if in /usr/share/dict/words, keep
#      actually this is a problem, because that source doesn't know about 'noblest' or 'tires'
#      use spacy or nltk
#   if spaCy flags as a person or place, keep
#   if it's not a word, but there is a word above some similarity threshold (AND levenshtein??), change
#   else drop

# Might also try *dropping* places but keeping people....although like "Jefferson"...

from argparse import ArgumentParser
from pathlib import Path

import gensim
import spacy

# this is terrible but so are relative imports in python
import sys
import os
sys.path.append(os.path.join(sys.path[0], '..'))

from utilities import initialize_logger

GENSIM_THRESHOLD = 0.6
LEVENSHTEIN_THRESHOLD = 2

def check_for_alternative(model, nlp, word):
    """
    The goal here is to remove words that are probably OCR errors and replace
    them with a likely candidate. The hope here is that this will minimize the
    chances that artifacts specific to particular digitization workflows will
    artificially group together documents, rather than documents being grouped
    on the basis of their underlying contents. Doubtless it will sometimes
    (frequently?) introduce errors, but since it's only substituting words that
    are fairly similar in meaning, that should only moderately affect downstream
    clustering.

    The threshold of 0.6 was chosen by looking at various real-world OCR errors
    and seeing their similarities to the correct word (typically .65-.75). The
    Levenshtein threshold, similarly.
    """
    options = model.wv.most_similar('word')
    thresholded_options = [opt[0] for opt in options if opt[1] > GENSIM_THRESHOLD]
    real_words = [word for word in thresholded_options if word in nlp.vocab.strings]
    
    import pdb; pdb.set_trace()


def filter(target_dir, model_path):
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        logging.info('The spaCy corpus is not available. `python -m spacy download en_core_web_sm` and try again.')
        import sys; sys.exit()

    model = gensim.models.Doc2Vec.load(model_path)

    for txt_file in Path(target_dir).rglob('*.txt'):
        with open(txt_file) as f:
            text = f.read()

        new_text = []

        print(f'handling {txt_file}')

        for word in text.split():
            # Keep things that are actually words. This includes proper nouns
            # such as place names.
            if word in nlp.vocab.strings:
                print(f'good word: {word}')
                new_text.append(word)
            else:
                word = check_for_alternative(model, nlp, word)
                if word:
                    new_text.append(word)



if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--target_dir', help='directory containing files to check')
    parser.add_argument('--model_path', help='path to neural net to use for word similarity')
    parser.add_argument('--logfile', default="filter_frontmatter.log")
    options = parser.parse_args()

    initialize_logger(options.logfile)

    filter(options.target_dir, options.model_path)

# for `canton`, 2-letter changes are common (e.g. 'cautou')
# >>> model.wv.most_similar('cautou')
# [('mis3', 0.6734908819198608), ('canton', 0.6474270224571228), ('jacksox',
# 0.6214158535003662), ('3m', 0.6087878942489624), ('cantox', 0.599487841129303),
# ('jackson', 0.5969511866569519), ('offick', 0.5901390910148621), ('6m',
# 0.5873024463653564), ('v7', 0.5811986923217773), ('osyka', 0.5809045433998108)]

# >>> model.wv.most_similar('frage')
# [('suffrage', 0.6635172367095947), ('baldness', 0.5722435712814331), ('fere',
# 0.5628131628036499), ('fering', 0.5568088293075562), ('rights',
# 0.5475192666053772), ('aggression', 0.5430271625518799), ('fered',
# 0.5414115786552429), ('citizenship', 0.5353204607963562), ('disa',
# 0.5345199108123779), ('inflicted', 0.5147979259490967)]
