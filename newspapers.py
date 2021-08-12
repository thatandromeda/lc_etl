from collections import defaultdict
import pickle
import re
from time import sleep

import requests

from slurp import http_adapter

newspapers_list = ["American Freedman", "Annual Cyclopedia",
    "Atlanta Constitution", "Atlantic Monthly", "Augusta Loyal Georgian",
    "Charleston Daily Republican", "Charleston News and Courier",
    "Charleston South Carolina Leader", "Christian Recorder",
    "Cincinnati Commercial", "Columbia Daily Phoenix", "Harper's Weekly",
    "Huntsville Advocate", "Jackson Mississippi Pilot",
    "Journal of Social Science", "Knoxville Whig",
    "Macon American Union", "Mobile Nationalist", "Mobile Register",
    "Montgomery Alabama State Journal", "Nashville Colored Tennessean",
    "Nashville Daily Press and Times", "National Anti-Slavery Standard",
    "National Freedman", "New National Era", "New Orleans Louisianian",
    "New Orleans Tribune", "New York Herald", "New York Journal of Commerce",
    "New York Times", "New York Tribune", "New York World",
    "North American Review", "Raleigh Daily Sentinel", "Raleigh Standard",
    "Richmond Dispatch", "Richmond New Nation", "Rural Carolinian",
    "Rutherford Star", "St. Landry Progress", "Savannah Daily News and Herald",
    "Savannah Freemen's Standard", "Savannah Weekly Republican",
    "Selma Southern Argus", "Southern Cultivator", "Southern Field and Factory",
    "Springfield Republican", "The Great Republic (Washington, D.C.)",
    "The Nation", "Tribune Almanac", "Washington Chronicle"]



# ~*~*~*~*~*~*~*~*~*~*~*~*~*~ find ALL the batches ~*~*~*~*~*~*~*~*~*~*~*~*~*~ #

# There's a one-to-many relationship between newspapers and lccns, and a
# many-to-many relationship between lccns and batches.
def create_lccn_to_batch():
    retval = defaultdict(set)
    batches = requests.get('https://chroniclingamerica.loc.gov/batches.json').json()
    iteration = 0

    while batches.get('next'):
        for batch in batches['batches']:
            lccns = batch['lccns']
            for lccn in lccns:
                retval[lccn].add(batch['name'])
        print(f'{iteration}: about to process {batches["next"]}')
        iteration += 1
        batches = requests.get(batches['next']).json()
        sleep(0.2)

    return retval

try:
    with open('lccn_to_batch', 'rb') as f:
        lccn_to_batch = pickle.load(f)
except:
    lccn_to_batch = create_lccn_to_batch()
    with open('lccn_to_batch', 'wb') as f:
        pickle.dump(lccn_to_batch, f)


# ~*~*~*~*~*~*~*~*~*~*~*~*~ get ALL the newspapers ~*~*~*~*~*~*~*~*~*~*~*~*~ #
def check_all_reconstruction_era_papers():
    more_to_go = True
    page = 1
    http = http_adapter()
    chronam_id = re.compile(r'/lccn/(\w+)/')
    all_lccns = set()
    while more_to_go == True:
        # You need all the query parameters, even the blank ones, or the API errors.
        url = f'https://chroniclingamerica.loc.gov/search/titles/results/?city=&rows=200&terms=&language=English&lccn=&material_type=&year1=1863&year2=1877&labor=&county=&state=&frequency=&page={page}&ethnicity=&sort=state&format=json'
        response = http.get(url).json()

        try:
            # ids are in format "/lccn/(lccn of item)"
            lccns = [chronam_id.match(item['id']).group(1) for item in response['items']]
            all_lccns.update(lccns)
        except Exception as e:
            import pdb; pdb.set_trace()
            raise

        print(f'page {page} processed')
        more_to_go = (response['endIndex'] < response['totalItems'])
        page += 1

        sleep(0.2)

    return all_lccns

try:
    with open('reconstruction_era_papers', 'rb') as f:
        all_lccns = pickle.load(f)
except:
    all_lccns = check_all_reconstruction_era_papers()
    with open('reconstruction_era_papers', 'wb') as f:
        pickle.dump(all_lccns, f)

# For future processing: https://github.com/lmullen/chronam-ocr-debatcher ?

# ~*~*~*~*~*~*~*~*~*~*~*~* narrow to relevant batches ~*~*~*~*~*~*~*~*~*~*~*~* #
def identify_batches_from_titles():
    all_batches_needed = set()
    available_newspapers = set()
    for newspaper in newspapers_list:
        name = newspaper.replace(' ', '+')
        response = requests.get(f'https://chroniclingamerica.loc.gov/suggest/titles/?q={name}')
        # The structure of the returned content is:
        # [search_term, [matching titles], [their lccns], [their urls]]
        lccns = response.json()[2]

        for lccn in lccns:
            batches = lccn_to_batch[lccn]
            if len(batches):
                available_newspapers.add(newspaper)
                all_batches_needed.update(batches)

    print(f'{len(available_newspapers)} newspapers found of {len(newspapers_list)} original titles')
    print(f'{len(all_batches_needed)} total batches needed')

    return all_batches_needed


def identify_batches_from_lccns():
    print('mapping lccns to batches...')
    all_batches_needed = set()
    available_lccns = set()
    for lccn in all_lccns:
        batches = lccn_to_batch[lccn]
        if len(batches):
            available_lccns.add(lccn)
            all_batches_needed.update(batches)

    print(f'{len(available_lccns)} newspapers found of {len(all_lccns)} original titles')
    print(f'{len(all_batches_needed)} total batches needed')

    return all_batches_needed

all_batches_needed = identify_batches_from_lccns()

# ~*~*~*~*~*~*~*~*~*~*~*~*~ narrow to usable batches ~*~*~*~*~*~*~*~*~*~*~*~*~ #
def restrict_to_ocred_batches():
    ocr_available = requests.get('https://chroniclingamerica.loc.gov/ocr.json').json()

    batch_to_url = {}
    for ocr in ocr_available['ocr']:
        # The batches just provide a batch name, but in the ocr file they're listed
        # as batch_name.tar.bz2.
        batch_to_url[(ocr['name']).split('.')[0]] = ocr['url']

    yay = 0
    boo = 0
    final_batches = []
    for batch in all_batches_needed:
        if batch_to_url.get(batch):
            yay += 1
            final_batches.append(batch)
        else:
            boo += 1
            print(f'not found for {batch}')

    print(f'found {yay}, could not find {boo}')


try:
    with open('chronam_batches_needed', 'rb') as f:
        final_batches = pickle.load(f)
except:
    final_batches = restrict_to_ocred_batches()
    with open('chronam_batches_needed', 'wb') as f:
        pickle.dump(final_batches, f)
