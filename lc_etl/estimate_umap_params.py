# load model
# iterate through newspapers
# every 1000 newspapers, check how many neighbors they have
# - pull top_n = 100
# - count everything over .65

from collections import Counter
from pathlib import Path

import gensim


def _get_doc2vec_tag(txt_path, target_dir):
    sub_path = txt_path.relative_to(target_dir)
    return str(sub_path).replace('ocr.txt', '').rstrip('/')


def estimate(target_dir, model_path, topn=100, threshold=0.65):
    model = gensim.models.Doc2Vec.load(model_path)
    count = 0
    stats = []

    for txt_path in Path(target_dir).rglob('**/*'):
        count += 1

        # Only sampling every thousandth file to save time.
        if not count % 1000 == 0:
            continue

        if not txt_path.is_file():
            continue

        # .DS_Store or whatever.
        if txt_path.name.startswith('.'):
            continue

        tag = _get_doc2vec_tag(txt_path, target_dir)

        try:
            neighbors = model.docvecs.most_similar(tag, topn=topn)
        except KeyError:
            print(f'Could not find {tag}')
            continue

        near_neighbors = [doc for doc in neighbors if doc[1] >= threshold]
        stats += [len(near_neighbors)]

    return {k: v for k, v in sorted(Counter(stats).items(), key=lambda item: item[1])}
