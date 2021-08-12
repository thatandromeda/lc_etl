from slurp import slurp, LocUrl

# Update slurp to take a url, and build_url to be more thoughtful about what
# can be built.
# If you want some syntactic sugar for slurp_by_subject or slurp_by_title, go
# for it.
# Deduplication??
# What I ultimately want out of this is:
# 1. A count of documents
# 2. A count of words
# 3. A list of subject headers (NOT deduplicated)

# Sources to look for:
# 1. The Foner papers
# 2. The Foner newspapers, limited to his date range
# 3. The collections suggested by Susan and Michelle (not newspapers), limited by date (and location?)
# 4. Reconstruction subject header
# 5. "Reconstruction" keyword in ChronAm, with some kind of date limiter?

titles_list = []
collections_list = []
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
papers_list = ["American Colonization Society", "Blair Family",
               "Benjamin H. Bristow", "Benjamin F. Butler",
               "William E. Chandler", "Salmon P. Chase", "William W. Clapp",
               "John Covode", "Henry L. Dawes", "James A. Garfield",
               "Andrew Johnson", "Manton Marble", "Carl Schurz", "John Sherman",
               "Thaddeus Stevens", "Lyman Trumbull", "Elihu B. Washburne"]
# oooh, I can't filter by date in the API, can I. I can *sort*, but not filter.
# wait maybe you can! ?dates=firstYear/lastYear, h/t Alice; this is INclusive

# Will I end up needing to train on LESS newspaper data so class imbalance
# issues don't hose me?
# how tf do I map this to bulk data, which is by batches named for awardees
# https://chroniclingamerica.loc.gov/newspapers.json lists all titles
# you can link that with lccn to batches https://chroniclingamerica.loc.gov/batches.json
# but not in an easy way
# and then batches are your bulk download
# for newspaper in newspapers_list:
#     print(f'NEWSPAPER: {newspaper}')
#     slurp(collection='chronicling america', title=newspaper)
# oooh but https://chroniclingamerica.loc.gov/newspapers.txt -- a list! Contains "Persistent Link | State | Title | LCCN | OCLC | ISSN | No. of Issues | First Issue Date | Last Issue Date | More Info"
# these are digitized
# https://chroniclingamerica.loc.gov/search/pages/results/?lccn=sn89053729&dateFilterType=yearRange&date1=1865&date2=1877
for title in titles_list:
    print(f'TITLE: {title}')
    slurp(query=title)


for collection in collections_list:
    print(f'COLLECTION: {collection}')
    slurp(collection=collection)

# This is sometimes yielding things of the form {$url: {'full_text': 'blah', 'etc': 'foo'}}
# %90 this does not just return american colonization society papers, it's an or, not an and, i hate this
for paper in papers_list:
    print(f'PAPER: {paper}')
    slurp(query=f'{paper} papers')
