import requests

from parse_lc_iiif_urls import full_text

def build_url(subject):
    subject = subject.replace(' ', '+')
    return 'https://www.loc.gov/search/?fo=json' \
           f'&fa=subject:{subject}' \
           '&fa=access-restricted:false' \
           '&fa=online-format:online-text|online-format:PDF' \
           '&c=100' \


def filter_results(response):
    results = response['results']
    return [
        result for result in results
        if (result.get('access_restricted') == False and
            isinstance(result.get('online_format'), list) and
            'online text' in result.get('online_format')) and
            'english' in result.get('language')
    ]



if __name__ == '__main__':
    url = build_url('african americans')
    response = requests.get(url).json()
    results = filter_results(response)
    for result in results:
        full_text(result)
