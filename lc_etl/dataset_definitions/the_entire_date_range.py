collections = []

date_filtered_collections = []

# EVERYTHING which is:
# 1865-1877
# in English
# from the US
# not a newspaper (ie it IS a different format) -- we'll get those from ChronAm
queries = [
    "https://www.loc.gov/books/?dates=1865/1877&fa=online-format:online+text%7Clocation:united+states",
    "https://www.loc.gov/manuscripts/?dates=1865/1877&fa=online-format:online+text%7Clocation:united+states",
    # These seem not to overlap with ChronAm, even though they are newspapers.
    "https://www.loc.gov/search/?dates=1865/1877&fa=online-format:online+text%7Clocation:united+states%7Coriginal-format:periodical",
    "https://www.loc.gov/notated-music/?dates=1865/1877&fa=online-format:online+text%7Clocation:united+states",
    "https://www.loc.gov/maps/?dates=1865/1877&fa=online-format:online+text%7Clocation:united+states",
    "https://www.loc.gov/photos/?dates=1865/1877&fa=online-format:online+text%7Clocation:united+states"
    # "https://www.loc.gov/search/?dates=1865/1877&fa=online-format:online+text&??fa=language:english%7Clocation:united+states"
]

items = []

# If unspecified, the default is set by lc_etl.newspapers.slurp_newspapers.
newspapers = {}
