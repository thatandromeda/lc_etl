if [ -z "$1" ]
  then
    echo "Must specify path to data definition"
    exit
fi

if [ -z "$2" ]
  then
    LOGFILE="pipeline_$(date +%Y%m%d_%H%M%S).log"
  else
    LOGFILE="$2"
fi
set -e

FILTER_DIR="filtered_newspapers"

# Back up previous data run.
mv newspapers old_newspapers
mv filtered_newspapers old_filtered_newspapers
mv results old_results

echo "Downloading data set..."
pipenv run python dataset.py --dataset_path=$1 --logfile=$LOGFILE

echo "Filtering newspapers..."
cp -r newspapers $FILTER_DIR
pipenv run python filter_frontmatter.py --target_dir=$FILTER_DIR --logfile=$LOGFILE
pipenv run python filter_ocr.py --target_dir=$FILTER_DIR --logfile=$LOGFILE

echo "Training neural net..."
pipenv run python train_doc2vec.py --newspaper_dir=$FILTER_DIR --logfile=$LOGFILE
model_name=$(basename `ls -t gensim_outputs/model* | head -1`)

echo "Generating embedding..."
pipenv run python embedding.py --model=gensim_outputs/${model_name} --logfile=$LOGFILE

echo "Downloading metadata..."
pipenv run python fetch_metadata.py --identifiers=viz/${model_name}_metadata.csv --logfile=$LOGFILE

echo "Preparing metadata..."
pipenv run python zip_csv.py --coordinates=viz/${model_name}_coordinates.csv --identifiers=viz/${model_name}_metadata.csv --output=viz/labeled_${model_name}.csv --logfile=$LOGFILE

echo "Preparing tiles..."
quadfeather --files=viz/labeled_${model_name}.csv --tile_size=20000 --destination viz/${model_name}_tiles
