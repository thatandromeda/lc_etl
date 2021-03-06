# Turn a model into a visualized embedding.

from argparse import ArgumentParser
import csv
import logging
from pathlib import Path

import gensim
import numpy as np
import pandas as pd
import umap.umap_ as umap
# import umap.plot

from .utilities import initialize_logger, BASE_DIR

OUTPUT_DIR = f'{BASE_DIR}/viz'

Path(f'./{OUTPUT_DIR}').mkdir(exist_ok=True)

def file_prefix(model):
    return Path(model).name


def make_embedding(model, n_neighbors, min_dist):
    logging.info('Generating embedding...')
    # n_components is how many dimensions the output should have.
    # 'cosine' is the distance metric used by Doc2Vec.
    umap_args = {'n_components': 2, 'metric': 'cosine'}
    # fit() returns an embedding (of type array) and a dict of auxiliary data;
    # fit_transform() returns just the embedding, normalized. I think.
    return umap.UMAP(**umap_args).fit_transform(model.dv.vectors)


# It will use labels for colors, which means we want to get/keep metadata on
# whatever we want to color by -- probably collection. We don't have that
# right now. Recycling code from another project to make it easy to find when
# needed.
# labels = []
# for k in list(model.doctags.keys()):
#     identifier = re.search(r'1721.1-(\d*).txt', k).group(1)
#     t = Thesis.objects.get(identifier=identifier)
#     try:
#       labels.append(t.department.first().name)
#     except:
#       labels.append('No Department')
# def show_plot(model, embedding):
#     hover_data = pd.DataFrame({'index': np.arange(len(model.dv)), 'label': model.dv.index_to_key})
#     umap.plot.output_file(f'{file_prefix()}_plot')
#     p = umap.plot.interactive(embedding, hover_data=hover_data, point_size=2) # fancy
#     umap.plot.show(p)

# Where we're at:
# the hover data is too big to display
# umap throws weird errors
# maybe it's time to think about deepscatter again

def write_to_tsv(model_path, embedding):
    """
    Output coordinates as a TSV file, suitable for use by deepscatter.
    """
    logging.info('Writing embedding coordinates')
    output_path = Path(OUTPUT_DIR).joinpath(f'{file_prefix(model_path)}_coordinates.csv')
    np.savetxt(output_path, embedding, delimiter=",",
               header="x\ty", comments='')


def write_metadata(model, model_path):
    """
    Write metadata for each of the data points to a tsv file, suitable for use
    by deepscatter.
    Note that this implicitly relies on Python list ordering -- the points
    represented in write_to_tsv must be in the same order!
    """
    logging.info('Writing embedding metadata')
    header = ['lccn']

    output_path = Path(OUTPUT_DIR).joinpath(f'{file_prefix(model_path)}_metadata.csv')

    with open(output_path, 'w', newline='') as f:
        csv_output = csv.writer(f, delimiter=',')
        csv_output.writerow(header)

        # This is a little silly now, but will be less silly when we have more
        # metadata.
        for key in model.dv.index_to_key:
            csv_output.writerow([key])


# The actual structure of the data set has a lot of nearby neighbors (per
# experiments with `estimate_umap_params`) -- potentially hundreds. That seems
# likely to produce something mushy-looking, though. I'll default to a high-ish
# n_neighbors value, and push the min_dist down to capture local similarities
# better. See https://umap-learn.readthedocs.io/en/latest/parameters.html .
def run(model_path, n_neighbors=100, min_dist= 0.001, logfile='embedding.log'):
    initialize_logger(logfile)

    model = gensim.models.Doc2Vec.load(model_path)
    embedding = make_embedding(model, n_neighbors, min_dist)
    write_to_tsv(model_path, embedding)
    write_metadata(model, model_path)
