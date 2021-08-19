from collections import defaultdict
import os
import pickle
import re
import requests
import shutil
import subprocess
from time import sleep

from queries import http_adapter

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

http = http_adapter()

# ~*~*~*~*~*~*~*~*~*~*~*~*~*~ find ALL the batches ~*~*~*~*~*~*~*~*~*~*~*~*~*~ #

# There's a one-to-many relationship between newspapers and lccns, and a
# many-to-many relationship between lccns and batches.
def create_lccn_to_batch():
    retval = defaultdict(set)
    batches = http.get('https://chroniclingamerica.loc.gov/batches.json').json()
    iteration = 0

    while batches.get('next'):
        for batch in batches['batches']:
            lccns = batch['lccns']
            for lccn in lccns:
                retval[lccn].add(batch['name'])
        print(f'{iteration}: about to process {batches["next"]}')
        iteration += 1
        batches = http.get(batches['next']).json()
        sleep(0.2)

    return retval


def get_lccn_to_batch():
    try:
        with open('lccn_to_batch', 'rb') as f:
            lccn_to_batch = pickle.load(f)
    except:
        lccn_to_batch = create_lccn_to_batch()
        with open('lccn_to_batch', 'wb') as f:
            pickle.dump(lccn_to_batch, f)

    return lccn_to_batch


# ~*~*~*~*~*~*~*~*~*~*~*~*~ get ALL the newspapers ~*~*~*~*~*~*~*~*~*~*~*~*~ #
def check_all_reconstruction_era_papers():
    more_to_go = True
    page = 1
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


def get_all_lccns():
    try:
        with open('reconstruction_era_papers', 'rb') as f:
            all_lccns = pickle.load(f)
    except:
        all_lccns = check_all_reconstruction_era_papers()
        with open('reconstruction_era_papers', 'wb') as f:
            pickle.dump(all_lccns, f)

    return all_lccns

# For future processing: https://github.com/lmullen/chronam-ocr-debatcher ?

# ~*~*~*~*~*~*~*~*~*~*~*~* narrow to relevant batches ~*~*~*~*~*~*~*~*~*~*~*~* #
# Not actually used, as it turns out.
def identify_batches_from_titles():
    all_batches_needed = set()
    available_newspapers = set()
    lccn_to_batch = get_lccn_to_batch()
    for newspaper in newspapers_list:
        name = newspaper.replace(' ', '+')
        response = http.get(f'https://chroniclingamerica.loc.gov/suggest/titles/?q={name}')
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
    all_lccns = get_all_lccns()
    lccn_to_batch = get_lccn_to_batch()
    for lccn in all_lccns:
        batches = lccn_to_batch[lccn]
        if len(batches):
            available_lccns.add(lccn)
            all_batches_needed.update(batches)

    print(f'{len(available_lccns)} newspapers found of {len(all_lccns)} original titles')
    print(f'{len(all_batches_needed)} total batches needed')

    return all_batches_needed


# ~*~*~*~*~*~*~*~*~*~*~*~*~ narrow to usable batches ~*~*~*~*~*~*~*~*~*~*~*~*~ #
def restrict_to_ocred_batches():
    ocr_available = http.get('https://chroniclingamerica.loc.gov/ocr.json').json()

    batch_to_url = {}
    for ocr in ocr_available['ocr']:
        # The batches just provide a batch name, but in the ocr file they're listed
        # as batch_name.tar.bz2.
        batch_to_url[(ocr['name']).split('.')[0]] = ocr['url']

    yay = 0
    boo = 0
    final_batches = []
    final_urls = []
    for batch in identify_batches_from_lccns():
        if batch_to_url.get(batch):
            yay += 1
            final_batches.append(batch)
            final_urls.append(batch_to_url[batch])
        else:
            boo += 1
            print(f'not found for {batch}')

    print(f'found {yay}, could not find {boo}')

    return final_batches, final_urls


def identify_chronam_downloads(arg):
    try:
        with open('chronam_batches_needed', 'rb') as f:
            final_batches = pickle.load(f)
        with open('chronam_urls_needed', 'rb') as f:
            final_urls = pickle.load(f)
    except:
        final_batches, final_urls = restrict_to_ocred_batches()
        with open('chronam_batches_needed', 'wb') as f:
            pickle.dump(final_batches, f)
        with open('chronam_urls_needed', 'wb') as f:
            pickle.dump(final_urls, f)

    return final_batches, final_urls

# ~*~*~*~*~*~*~*~*~*~*~*~*~ fetch batches ~*~*~*~*~*~*~*~*~*~*~*~*~ #
tmpzip = 'tmpzip.zip'
newspaper_dir = 'newspapers'

def make_newspaper_dir():
    try:
        os.mkdir(newspaper_dir)
    except FileExistsError:
        pass


def get_batch_to_lccn():
    batch_to_lccn = defaultdict(set)
    lccn_to_batch = get_lccn_to_batch()
    for lccn, batchlist in lccn_to_batch.items():
        # We don't need the list comprehension output -- it's just a quick way to
        # handle inverting this data structure. We care about the final
        # batch_to_lccn.
        [batch_to_lccn[batch].add(lccn) for batch in batchlist]

    return batch_to_lccn


# The endpoint is exclusive, so this matches dates from 1863 through 1877.
def slurp_newspapers(goal_dates=range(1863, 1878)):
    make_newspaper_dir()
    batch_to_lccn = get_batch_to_lccn()
    final_batches, final_urls = identify_chronam_downloads()

    batch_match = re.compile(r'/([\w_]+).tar.bz2')

    for url in final_urls:
        print(f'Downloading {url}...')
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(tmpzip, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        batch_name = batch_match.search(url).group(1)
        output_dirs = batch_to_lccn[batch_name]

        print(f'....Extracting {url}')
        subprocess.call(f'tar -xf {tmpzip} -C {newspaper_dir}', shell=True)

        print(f'....Removing extraneous directories')
        for output_dir in output_dirs:
            for subdir in os.listdir(os.path.join(newspaper_dir, output_dir)):
                if int(subdir) not in goal_dates:
                    shutil.rmtree(os.path.join(newspaper_dir, output_dir, subdir))

        subprocess.call(f'rm {tmpzip}', shell=True)

# The above works BUT it eats your entire disk, so cloud it and/or make it a
# streaming thing. Also you might want to pick a subset because class imbalance.
# Also if you're picking a subset to be on par with other things you may need
# to think about pretrained vectors, for all that they are a problem.
# Delete all empty subdirectories of newspaper_dir.
# Because a batch may contain multiple lccns, it may contain newspapers that
# don't satisfy the date range criterion (along with one or more that do),
# resulting in empty directories.

# FOR NOW we will keep all of the ed/seq separate and not try to unite issues
# Similarly we will not try to handle the same lccn appearing in more than one
# batch -- implicitly we end up with the latest batch being available here.
