# This removes the first $NUMBER lines from all files in the provided directory.
# This will remove much, but not always all, of the archival notes content,
# while leaving most, but usually not all, of the real content in place.

NUMBER=10
while getopts "p:n:h" opt; do
  case $opt in
      p)
        WORKING_PATH="$OPTARG"
        ;;
      n)
        NUMBER="$OPTARG"
        ;;
      h)
        echo "-p path/to/content        (required)"
        echo "-n number of initial lines to delete (optional; defaults to 10)"
        exit
        ;;
    esac
done

if [ -z "$WORKING_PATH" ]
  then
    echo "Path to content must be provided with -p"
    exit
fi

COUNT=`find ${WORKING_PATH} -type f | wc -l`

if [[ "$OSTYPE" == "darwin20" ]]; then
  find ${WORKING_PATH} -type f -exec sed -i '' "1,${NUMBER}d" {} \;
else
  find ${WORKING_PATH} -type f -exec sed -i "1,${NUMBER}d" {} \;
fi

if [[ "$COUNT" == 1 ]]; then
  echo "1 file edited"
else
  echo "${COUNT} files edited"
fi
