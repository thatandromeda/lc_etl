import sys
from urllib.parse import urlparse

from locr import Fetcher
import requests

from slurp import paginate_search, filter_results, filenamify

# collections = ["https://www.loc.gov/collections/abraham-lincoln-papers/",
#                "https://www.loc.gov/collections/salmon-p-chase-papers/",
#                "https://www.loc.gov/collections/james-a-garfield-papers/",
#                "https://www.loc.gov/collections/andrew-johnson-papers/",
#                "https://www.loc.gov/collections/frederick-douglass-papers/",
#                "https://www.loc.gov/collections/thaddeus-stevens-papers/",
#                "https://www.loc.gov/collections/e-b-washburne-papers/",
#                "https://www.loc.gov/collections/anna-e-dickinson-papers/",
#                "https://www.loc.gov/collections/alexander-hamilton-stephens-papers/",
#                "https://www.loc.gov/collections/ulysses-s-grant-papers/",
#                "https://www.loc.gov/collections/philip-henry-sheridan-papers/",
#                "https://www.loc.gov/collections/frederick-douglass-papers/",
#                "https://www.loc.gov/collections/edwin-mcmasters-stanton-papers/",
#                "https://www.loc.gov/collections/slave-narratives-from-the-federal-writers-project-1936-to-1938/"]

collections = ["https://www.loc.gov/collections/slave-narratives-from-the-federal-writers-project-1936-to-1938/"]

other_collections = ["https://www.loc.gov/item/29009286/",
                     "https://www.loc.gov/search/?fa=contributor:american+colonization+society"]


# OH MY GOD the Lincoln ones have IIIF URLs but they are found under storage-services URLs
# auuuuuugh
# ugh. gonna have to redo Fetcher so it makes an intelligent guess, but then iterates through everything, huh
# or turn it into a web scraper
# no! look for [resources][fulltext_file]...use that if you can
# and then use resources to choose a fetcher with the right parse_text option
found = 0
total_words = 0
total_docs = 0
for base_url in collections:
    last_found = found
    last_words = total_words
    url = f'{base_url}search/?fa=online-format:online+text&fo=json'
    for response in paginate_search(url):
        results = filter_results(response)
        for result in results:
            total_docs += 1
            try:
                fetcher = Fetcher(result)

                text = fetcher.full_text()
                if text:
                    found += 1
                    total_words += len(text.split(' '))

                    with open(filenamify(result), 'w') as f:
                        f.write(text)
            except:
                import pdb; pdb.set_trace()
                print(f'No dice for {result["id"]}')

    print(f'for collection {base_url}...')
    print(f'{found-last_found} documents found; {total_words-last_words} words')

print(f'{found} documents found of {total_docs} total; {total_words} total words')
