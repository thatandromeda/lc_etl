# The pattern passed to grep indicates that archivists' notes are contained
# within the fulltext file.
# There is not a consistent boundary between notes and fulltext. Furthermore,
# notes and fulltext may be interspersed. (The reason for this is that the
# original digitized content may have been a folder containing both papers and
# archival records, all of whose contents were digitized. See, e.g.,
# https://www.loc.gov/item/mss18630.03661.)
# As there is not a programmatic way to separate out only the actual content,
# it's easiest to just delete any of these files.

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

COUNT=`find ${WORKING_PATH} -type f -exec grep -E "Box [0-9]+[[:space:]]+Folder [0-9]+" {} \; | wc -l`

find ${WORKING_PATH} -type f -exec grep -E "Box [0-9]+[[:space:]]+Folder [0-9]+" {} \; -delete

if [[ "$COUNT" == 1 ]]; then
  echo "1 file deleted"
else
  echo "${COUNT} files deleted"
fi
