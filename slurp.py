import shutil
from urllib.parse import urlparse

import cv2
import layoutparser as lp
import pytesseract
import requests

OCR_AGENT = lp.ocr.TesseractAgent(languages='eng')

pytesseract.pytesseract.tesseract_cmd = '/usr/local/bin/tesseract' # todo: configurable?

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


def file_ext_from_url(image_url):
    return urlparse(image_url).path.split('.')[-1].upper()


def write_image(image_url, tmpfilename):
    response = requests.get(image_url, stream=True)
    with open(tmpfilename, 'wb') as f:
        response.raw.decode_content = True
        shutil.copyfileobj(response.raw, f)


def parse_text(result):
    image_urls = result['image_url']    # type `list`
    for image_url in image_urls:
        tmpfilename = f'tmp.{file_ext_from_url(image_url)}'
        write_image(image_url, tmpfilename)
        image = cv2.imread(tmpfilename)
        ocr_response = OCR_AGENT.detect(image, return_response=True)
        import pdb; pdb.set_trace()


if __name__ == '__main__':
    url = build_url('african americans')
    response = requests.get(url).json()
    results = filter_results(response)
    for result in results:
        parse_text(result)
