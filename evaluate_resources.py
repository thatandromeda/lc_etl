from lc_text_fetcher import Fetcher
from slurp import build_url, filter_results, paginate_search

url = build_url('aircraft accidents')
matched = 0
unmatched = 0

for response in paginate_search(url):
    results = filter_results(response)
    for result in results:
        for image_url in result['image_url']:
            result_handler = Fetcher(result)._get_handler(image_url)
            image_path = result_handler.extract_image_path()
            constructed_urls = [result_handler.request_url(image_path)]
            try:
                constructed_urls.append(result_handler.alternate_url(image_path))
            except:
                pass
            provided_urls = [
                r.get('fulltext_file') for r in result['resources']
            ]
            if set(constructed_urls) & set(provided_urls):
                matched += 1
            else:
                unmatched += 1
                print(result['id'])
                print(constructed_urls)
                print(provided_urls)
                print("\n")

    print(f'Matched: {matched}; unmatched: {unmatched}')
    break
