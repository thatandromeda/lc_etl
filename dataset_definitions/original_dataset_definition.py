collections = [
    "https://www.loc.gov/collections/abraham-lincoln-papers/",
    "https://www.loc.gov/collections/slave-narratives-from-the-federal-writers-project-1936-to-1938/"
]

date_filtered_collections = [
    # supreme court opinions
    "https://www.loc.gov/collections/united-states-reports/",
    # this is https://memory.loc.gov/ammem/amlaw/lwsl.html
    "https://www.loc.gov/collections/united-states-statutes-at-large/"
]

queries = [
    "https://www.loc.gov/search/?fa=contributor:american+colonization+society",
    "https://www.loc.gov/collections/broadsides-and-other-printed-ephemera/?q=reconstruction+OR+%22ex-slave%22",
    "https://www.loc.gov/collections/broadsides-and-other-printed-ephemera/?q=colored+OR+negro+OR+South+OR+Congress&dates=1863/1877",
    "https://www.loc.gov/search/?fa=subject:african-american+history|online-format:online+text&dates=1863/1877",
    "https://www.loc.gov/search/?fa=subject:african+american|online-format:online+text&dates=1863/1877",
    "https://www.loc.gov/search/?fa=subject:african+american+history|online-format:online+text&dates=1863/1877",
    "https://www.loc.gov/search/?fa=subject:black+history|online-format:online+text&dates=1863/1877",
    "https://www.loc.gov/search/?fa=subject:reconstruction|online-format:online+text",
    "https://www.loc.gov/search/?fa=partof:american+memory|online-format:online+text&dates=1863/1877",
    "https://www.loc.gov/collections/rare-book-selections/?fa=language:english|online-format:online+text|location:united+states&dates=1863/1877",
    "https://www.loc.gov/search/?dates=1863/1877&fa=online-format:online+text%7Cpartof:rare+book+and+special+collections+division",
    ]

# The first item in the list has fulltext but it's not being fetched -- we're
# gonna need to add a fetcher. Hold off on that until we can consult logs for
# all the things not fetched.
items = ["https://www.loc.gov/item/29009286/",
         "https://www.loc.gov/item/rbpe.18704800/",
         "https://www.loc.gov/item/rbpe.24001000/"]

# In need of further processing:
# https://www.loc.gov/collections/selected-digitized-books/?dates=1863/1877&fa=language:english%7Conline-format:online+text%7Clocation:united+states
