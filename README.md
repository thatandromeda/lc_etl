Setup:
- git clone
- `cd lc_etl`
- `pipenv install`

Workflow for getting data from LOC into a model, and transforming that model into a format that can be represented on the web:

- edit `dataset.py` as needed to specify desired items/collections
- `pipenv run python dataset.py` (gets the fulltext data)
- `pipenv run python train_doc2vec.py` (trains the neural net)
- `pipenv run python embedding.py` (projects the neural net down to a 2d embedding)
- edit `fetch_metadata.py` so that the filename/timestamp matches the just-created file
- `pipenv run python fetch_metadata.py` (gets the metadata)
  - A more efficient version would combine this with fetching the dataset, but I've been developing this one step of the pipeline at a time for ease of troubleshooting
- `pipenv run zip_csv.py` (combines embedding vectors with metadata, into a csv suitable for use by quadfeather)
- `quadfeather --files viz/labeled_model.csv --tile_size 10000 --destination viz/lc_etl_tiles`
  - The arguments can be different if you prefer

To load a model, in order to explore it:
- `pipenv run python`
- `>>> import gensim`
- `>>> model = gensim.models.Doc2Vec.load("path/to/model")`
