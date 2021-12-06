# Set defaults.
LOGFILE="pipeline_$(date +%Y%m%d_%H%M%S).log"
BASE_DIR="lc_etl"

while getopts "d:l:b:c:h" opt; do
  case $opt in
      d)
        DATADEF="$OPTARG"
        ;;
      l)
        LOGFILE="$OPTARG"
        ;;
      b)
        BASE_DIR="$OPTARG"
        ;;
      c)
        CONFIG_FILE="$OPTARG"
        ;;
      h)
        echo "-d path/to/data/definition        (required)"
        echo "-l logfile                        (optional; has timestamped default)"
        echo "-b base directory                 (optional; defaults to lc_etl)"
        echo "-c ML training config file        (optional)"
        echo "-h print this message and exit    (optional)"
        exit
        ;;
    esac
done

if [ -z "$DATADEF" ]
  then
    echo "Data definition must be provided"
    exit
fi
set -e

FILTER_DIR="${BASE_DIR}/filtered_newspapers"

# Back up previous data run.
[ -f newspapers ] && mv newspapers old_newspapers
[ -f filtered_newspapers ] && mv filtered_newspapers old_filtered_newspapers
[ -f results ] && mv results old_results

echo "Downloading data set..."
pipenv run python lc_etl/dataset.py --dataset_path=$DATADEF --logfile=$LOGFILE

echo "Filtering newspapers..."
cp -r newspapers $FILTER_DIR
pipenv run python lc_etl/filter_frontmatter.py --target_dir=$FILTER_DIR --logfile=$LOGFILE
pipenv run python lc_etl/filter_ocr.py --target_dir=$FILTER_DIR --logfile=$LOGFILE

echo "Training neural net..."
pipenv run python lc_etl/train_doc2vec.py --config_file=${CONFIG_FILE} --logfile=$LOGFILE
model_name=$(basename `ls -t ${BASE_DIR}/gensim_outputs/model* | head -1`)

echo "Generating embedding..."
pipenv run python lc_etl/embedding.py --model=${BASE_DIR}/gensim_outputs/${model_name} --logfile=$LOGFILE

echo "Downloading metadata..."
pipenv run python lc_etl/fetch_metadata.py --identifiers=${BASE_DIR}/viz/${model_name}_metadata.csv --logfile=$LOGFILE

echo "Preparing metadata..."
pipenv run python lc_etl/zip_csv.py --coordinates=${BASE_DIR}/viz/${model_name}_coordinates.csv --identifiers=${BASE_DIR}/viz/${model_name}_metadata.csv --output=${BASE_DIR}/viz/labeled_${model_name}.csv --logfile=$LOGFILE

echo "Preparing tiles..."
pipenv run quadfeather --files=${BASE_DIR}/viz/labeled_${model_name}.csv --tile_size=10000 --destination=${BASE_DIR}/viz/${model_name}_tiles
