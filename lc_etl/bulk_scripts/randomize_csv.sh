# The csv, as originally generated, is in the same order that items were
# fetched in from the API. This means that the first tile (i.e. the one seen on
# load) is likely to be composed of items from the same collection. This makes
# it hard to see the overall structure of the data. It's better to randomize
# the order of items in the file, so that the first tile can contain
# representatives from lots of parts of the graph. Probabilistically, dense
# parts of the graph are likely to have more representation too, so the visual
# impression should be indicative of the underlying structure.

while getopts "c:h" opt; do
  case $opt in
      c)
        FILENAME="$OPTARG"
        ;;
      h)
        echo "-c path/to/csvfile        (required)"
        exit
        ;;
    esac
done

if [ -z "$FILENAME" ]
  then
    echo "Path to content must be provided with -c"
    exit
fi

OUTPUT='tmp.csv'

# Make sure to keep the first line (the csv header) as the first line!
head -n 1 $FILENAME > $OUTPUT

if [[ "$OSTYPE" == "darwin20" ]]; then
  sed -i '' "1d" $FILENAME
else
  sed -i "1d" $FILENAME
fi

# Now that we've preserved the header, shuffle & append the contents.
shuf $FILENAME >> $OUTPUT

mv $OUTPUT $FILENAME
