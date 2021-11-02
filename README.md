Setup:
- git clone
- `cd lc_etl`
- `pipenv install`

Workflow for getting data from LOC into a model, and transforming that model into a format that can be represented on the web:

- edit `dataset.py` as needed to specify desired items/collections
- `./run_pipeline.sh path/to/dataset`
  - optionally, you may add a second command-line argument to specify a logfile (if you do not, it will use a default timestamped value)

This pipeline script performs the following steps, which you may also run separately:
- `pipenv run python dataset.py` (gets the fulltext data)
- Consider copying the newspapers to a backup directory before you run the filters on them.
- `pipenv run python filter_frontmatter.py --target_dir=(wherever your newspapers are)`
- `pipenv run python filter_ocr.py --target_dir=(wherever your newspapers are)`
  - You probably want to run this as `nohup pipenv run python filter_ocr.py --target_dir=(wherever)`. It's long.
- `pipenv run python train_doc2vec.py` (trains the neural net)
  - `--newspaper_dir` (optional) specifies directory containing newspapers (default: `newspapers`)
- `pipenv run python embedding.py --model=/path/to/model` (projects the neural net down to a 2d embedding)
- `pipenv run python fetch_metadata.py --identifiers=/path/to/embedding/output` (gets the metadata)
  - `embedding.py` will have output a file with a name like `model_20211027_150539_metadata.csv`; use that name here
  - A more efficient version would combine this with fetching the dataset, and/or cache previously fetched metadata somewhere, but I've been developing this one step of the pipeline at a time for ease of troubleshooting
- `pipenv run python zip_csv.py --coordinates=path/to/coordinates/csv --identifiers=path/to/identifiers/csv --output=desired/path/of/output/csv` (combines embedding vectors with metadata, into a csv suitable for use by quadfeather)
- `quadfeather --files viz/labeled_model.csv --tile_size 10000 --destination viz/lc_etl_tiles`
  - The arguments can be different if you prefer

Some of these (`train_doc2vec` in particular) may be time-consuming, so you might want to run them with `nohup`, or whatever you like for being able to walk away from a process for a while.

To load a model, in order to explore it:
- `pipenv run python`
- `>>> import gensim`
- `>>> model = gensim.models.Doc2Vec.load("path/to/model")`
