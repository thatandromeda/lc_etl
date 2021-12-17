# Set defaults.
LOGFILE="comprehensive_filtering.log"
BASE_DIR="lc_etl"
DATADEF="lc_etl/dataset_definitions/non_chronam_only.py"

FILTER_DIR="${BASE_DIR}/newspapers_full_filtering_pipeline_test"
RESULTS_DIR="${BASE_DIR}/results_full_filtering_pipeline_test"
METADATA_DIR="${BASE_DIR}/metadata"

MODEL_PATH="${BASE_DIR}/gensim_outputs/model_test_🎉_20211206_132918"

# These were derived by looking at the indexes of Foner's and Du Bois's books
# on Reconstruction to find single-word terms which were unusually frequent.
# This explicitly excludes proper nouns that occur frequently (notably, states,
# many of which were very frequent index terms, but all of which are accounted
# for via conventional metadata).
# I expect some of these will be duplicative (e.g. "suffrage" and "equality"
# are likely similar), but I want to cast a wide net here in hopes of ending up
# with some useful options for visualization.
BASE_WORDS="abolition,rights,election,education,suffrage,school,convention,property,worker,labor,freedmen,agriculture,business,representation,constitution,economy,equality,yeoman"

set -e

# This pipeline is broken into groups of scripts that may run in parallel (e.g.
# since I am reusing already-downloaded newspapers, I can download their
# metadata while I wait for the non-newspaper-only dataset to finish
# downloading). The ampersands allow the processed to be
# backgrounded/parallelized. However, each group contains steps that block
# subsequent groups (e.g. all content must be downloaded before it can be
# filtered). The wait statements ensure that blockers will be done before next
# steps execute.

# ------------- First: download all data & metadata we will need ------------- #
echo "Downloading data set..."
pipenv run python lc_etl/dataset.py --dataset_path=$DATADEF --logfile=$LOGFILE &

pipenv run python lc_etl/fetch_metadata.py --newspaper_dir=$FILTER_DIR --logfile=$LOGFILE --overwrite=True &
wait

cp -r lc_etl/results $RESULTS_DIR

pipenv run python lc_etl/fetch_metadata.py --results_dir=$RESULTS_DIR --logfile=$LOGFILE --overwrite=True &


# ------------------------------ Filter nonwords ----------------------------- #
echo "Filtering newspaper OCR..."
pipenv run python lc_etl/filter_ocr.py --target_dir=$FILTER_DIR --logfile=$LOGFILE &
echo "Filtering result OCR..."
pipenv run python lc_etl/filter_ocr.py --target_dir=$RESULTS_DIR --logfile=$LOGFILE &

wait


# ----------------------------- Remove frontmatter --------------------------- #
echo "Removing newspaper frontmatter..."
./lc_etl/bulk_scripts/remove_frontmatter.sh -p $FILTER_DIR &

echo "Removing archival notes gently..."
./lc_etl/bulk_scripts/remove_archival_notes_gentle.sh -p $RESULTS_DIR &

wait


# ---------------------------- Remove attributions --------------------------- #
echo "Removing transcription attributions..."
./lc_etl/bulk_scripts/remove_transcription_attribution.sh -p $RESULTS_DIR


# ------------------------------ Filter nonwords ----------------------------- #
echo "Filtering newspaper nonwords..."
pipenv run python lc_etl/filter_nonwords.py --target_dir=$FILTER_DIR --model_path=$MODEL_PATH --logfile=$LOGFILE &

echo "Filtering result nonwords..."
pipenv run python lc_etl/filter_nonwords.py --target_dir=$RESULTS_DIR --model_path=$MODEL_PATH --logfile=$LOGFILE &

wait


# ----------------------------- Filter locations ----------------------------- #
echo "Filtering newspaper locations..."
pipenv run python lc_etl/filter_newspaper_locations.py --target_dir=$FILTER_DIR --metadata_dir=$METADATA_DIR--logfile=$LOGFILE


# ----------------------------- Train neural net ----------------------------- #
echo "Training neural net..."
pipenv run python lc_etl/train_doc2vec.py --config_file=${CONFIG_FILE} --logfile=$LOGFILE
model_name=$(basename `ls -t ${BASE_DIR}/gensim_outputs/model* | head -1`)


# ------------------------ Assign similarity metadata ------------------------ #
echo "Assigning similarity metadata..."
# Note that we use the newly trained model for this, not the intermediate model
# that we necessarily used for nonword filtering.
pipenv run python lc_etl/assign_similarity_metadata.py --model_path=${BASE_DIR}/gensim_outputs/${model_name} --metadata_dir=$METADATA_DIR --newspaper_dir=$FILTER_DIR --results_dir=$RESULTS_DIR --logfile=$LOGFILE --base_words=$BASE_WORDS


# --------------------------- Generate viz outputs --------------------------- #
echo "Generating embedding..."
pipenv run python lc_etl/embedding.py --model=${BASE_DIR}/gensim_outputs/${model_name} --logfile=$LOGFILE

echo "Preparing metadata..."
pipenv run python lc_etl/zip_csv.py --coordinates=${BASE_DIR}/viz/${model_name}_coordinates.csv --identifiers=${BASE_DIR}/viz/${model_name}_metadata.csv --output=${BASE_DIR}/viz/labeled_${model_name}.csv --logfile=$LOGFILE

echo "Preparing tiles..."
pipenv run quadfeather --files=${BASE_DIR}/viz/labeled_${model_name}.csv --tile_size=10000 --destination=${BASE_DIR}/viz/${model_name}_tiles
