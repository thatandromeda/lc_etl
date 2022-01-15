from pathlib import Path
import shutil
import subprocess

from lc_etl import (dataset, fetch_metadata, filter_ocr, filter_nonwords,
                    filter_newspaper_locations, train_doc2vec,
                    assign_similarity_metadata, embedding, zip_csv)
from lc_etl.utilities import DEFAULT_NEWSPAPER_DIR, DEFAULT_RESULTS_DIR

# Set defaults.
LOGFILE="everything.log"
BASE_DIR="lc_etl/data"
DATADEF="lc_etl/dataset_definitions/the_entire_date_range.py"

FILTER_DIR=f"{BASE_DIR}/newspapers_everything"
RESULTS_DIR=f"{BASE_DIR}/results_everything"
METADATA_DIR=f"{BASE_DIR}/metadata"

BOOTSTRAP_MODEL_PATH=f"{BASE_DIR}/gensim_outputs/model_test_🎉_20211206_132918"
CONFIG_FILE="lc_etl.config_files.everything"

# These were derived by looking at the indexes of Foner's and Du Bois's books
# on Reconstruction to find single-word terms which were unusually frequent.
# This explicitly excludes proper nouns that occur frequently (notably, states,
# many of which were very frequent index terms, but all of which are accounted
# for via conventional metadata).
# I used a longer list for a first pass, and then deleted ones that didn't seem
# useful in surfacing clusters (i.e. not much color variation).
BASE_WORDS="abolition,agriculture,business,constitution,convention,economy,education,election,equality,freedmen,labor,property,suffrage,worker"

# ------------- First: download all data & metadata we will need ------------- #
print("Downloading data set...")
dataset.fetch(dataset_path=DATADEF, logfile=LOGFILE)

shutil.copytree(Path(BASE_DIR) / DEFAULT_RESULTS_DIR, RESULTS_DIR)
shutil.copytree(Path(BASE_DIR) / DEFAULT_NEWSPAPER_DIR, RESULTS_DIR)

fetch_metadata.run(results_dir=RESULTS_DIR, newspaper_dir=FILTER_DIR, logfile=LOGFILE, overwrite=False)


# ------------------------------ Filter bad OCR ------------------------------ #
print("Filtering newspaper OCR...")
filter_ocr.run(target_dir=FILTER_DIR, logfile=LOGFILE)

print("Filtering result OCR...")
filter_ocr.run(target_dir=RESULTS_DIR, logfile=LOGFILE)


# ----------------------------- Remove frontmatter --------------------------- #
print("Removing newspaper frontmatter...")
subprocess.run(f'/lc_etl/bulk_scripts/remove_frontmatter.sh -p {FILTER_DIR}', shell=True)

print("Removing archival notes gently...")
subprocess.run(f'./lc_etl/bulk_scripts/remove_archival_notes_gentle.sh -p {RESULTS_DIR}', shell=True)


# ---------------------------- Remove attributions --------------------------- #
print("Removing transcription attributions...")
subprocess.run(f'./lc_etl/bulk_scripts/remove_transcription_attribution.sh -p {RESULTS_DIR}', shell=True)


# ------------------------------ Filter nonwords ----------------------------- #
print("Filtering newspaper nonwords...")
filter_nonwords.run(target_dir=FILTER_DIR, model_path=BOOTSTRAP_MODEL_PATH, logfile=LOGFILE)

print("Filtering result nonwords...")
filter_nonwords.run(target_dir=RESULTS_DIR, model_path=BOOTSTRAP_MODEL_PATH, logfile=LOGFILE)


# ----------------------------- Filter locations ----------------------------- #
print("Filtering newspaper locations...")
filter_newspaper_locations.run(target_dir=FILTER_DIR, metadata_dir=METADATA_DIR, logfile=LOGFILE)


# ---------------------------- Remove empty files ---------------------------- #
print("Removing empty files and directories...")
subprocess.run(f'find {FILTER_DIR} -type f -empty -delete', shell=True)
subprocess.run(f'find {FILTER_DIR} -mindepth 1 -type d -empty -delete', shell=True)
subprocess.run(f'find {RESULTS_DIR} -type f -empty -delete', shell=True)


----------------------------- Train neural net ----------------------------- #
print("Training neural net...")
train_doc2vec.run(config_file=CONFIG_FILE, logfile=LOGFILE)
model_name = subprocess.run(
    f'basename `ls -t {BASE_DIR}/gensim_outputs/model* | head -1`',
    shell=True, check=True, stdout=subprocess.PIPE
).stdout.decode('utf-8').strip()


# ------------------------ Assign similarity metadata ------------------------ #
print("Assigning similarity metadata...")
# Note that we use the newly trained model for this, not the intermediate model
# that we necessarily used for nonword filtering.
model_path = str(Path(BASE_DIR) / 'gensim_outputs' / model_name)
assign_similarity_metadata.run(
    model_path=str(model_path), metadata_dir=METADATA_DIR,
    newspaper_dir=FILTER_DIR, results_dir=RESULTS_DIR,
    logfile=LOGFILE, base_words=BASE_WORDS)


# --------------------------- Generate viz outputs --------------------------- #
print("Generating embedding...")
embedding.run(model_path=model_path, logfile=LOGFILE)

print("Preparing metadata...")
coordinates = Path(BASE_DIR) / 'viz' / f'{model_name}_coordinates.csv'
identifiers = Path(BASE_DIR) / 'viz' / f'{model_name}_metadata.csv'
zipped_csv = Path(BASE_DIR) / 'viz' / f'labeled_{model_name}.csv'
zip_csv.run(coordinates=coordinates, identifiers=identifiers, output=zipped_csv, logfile=LOGFILE)

print("Shuffling metadata...")
subprocess.run(f'./lc_etl/bulk_scripts/randomize_csv.sh -c {zipped_csv}', shell=True)

print("Preparing tiles...")
destination = Path(BASE_DIR) / 'viz' / f'{model_name}_tiles'
# We need to coerce the type of date to string; pyarrow otherwise infers type
# date32, and errors when it encounters dates that are only yyyy (instead of
# yyyy-mm-dd). The downstream consumer should be fine either way.
# The below invocation is temporarily broken
#tiler.main(["--files", zipped_csv, '--destination', destination, '--dtypes', 'date=string', '--tile_size', '25000'])
subprocess.run(f"pipenv run quadfeather --files={zipped_csv} --destination={destination} --dtypes 'date=string' --tile_size=25000", shell=True)
