while getopts "p:h" opt; do
  case $opt in
      p)
        WORKING_PATH="$OPTARG"
        ;;
      h)
        echo "-p path/to/content        (required)"
        exit
        ;;
    esac
done

if [ -z "$WORKING_PATH" ]
  then
    echo "Path to content must be provided with -p"
    exit
fi

TO_DELETE="Transcribed and reviewed by contributors participating in the By The People project at crowd.loc.gov"

COUNT=`find ${WORKING_PATH} -type f -exec grep -E "${TO_DELETE}" {} \; | wc -l`

if [[ "$OSTYPE" == "darwin20" ]]; then
  find ${WORKING_PATH} -type f -exec sed -i '' "/${TO_DELETE}/d" {} \;
else
  find ${WORKING_PATH} -type f -exec sed -i "/${TO_DELETE}/d" {} \;
fi

if [[ "$COUNT" == 1 ]]; then
  echo "1 file edited"
else
  echo "${COUNT} files edited"
fi
