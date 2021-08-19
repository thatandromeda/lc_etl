import logging
import subprocess

from locr import Fetcher

from queries import slurp, http_adapter, jsonify, filenamify, record_subjects

logging.basicConfig(filename=f'notfound.log')

def slurp_items(items):
    """
    Takes a list of item URLs and writes the item full_text, if available.

    The `fo=json` parameter for the URL is optional; it will be supplied if
    absent.
    """
    http = http_adapter()

    for item in items:
        print(f'PROCESSING: {item}')
        url = jsonify(item)
        response = http.get(url).json()
        result = response['item']
        text = Fetcher(result).full_text()

        record_subjects(result)

        if text:
            print(filenamify(result))
            with open(filenamify(result), 'w') as f:
                f.write(text)
        else:
            logging.warning(f'WAT: Could not locate text for {result["id"]}')
