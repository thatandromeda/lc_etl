import argparse
from dataclasses import dataclass
import json
import shutil
import unittest

import responses

from lc_etl.fetch_metadata import fetch
# arrange, act, assert

@dataclass
class Arguments:
    identifiers: str


class TestMetadataFetching(unittest.TestCase):
    def setUp(self):
        self.responses = responses.RequestsMock(
            # Must match the namespace of the thing actually issuing the
            # request! Without this, it defaults to mocking the requests
            # library, and only matches on things sent in this file by
            # requests.get().
            target="lc_etl.utilities.http_adapter"
        )
        self.responses.start()

        # self.responses.add(...)

        self.addCleanup(self.responses.stop)
        self.addCleanup(self.responses.reset)


    @unittest.mock.patch('lc_etl.fetch_metadata.OUTPUT_DIR', 'tests/metadata')
    def test_fetches_data_for_chronam(self):
        identifier = 'sn88053082'
        with open(f'tests/{identifier}.json', 'r') as f:
            responses.add(
                responses.GET,
                f'https://www.loc.gov/item/{identifier}/?fo=json',
                json=json.load(f),
            )
        fetch(Arguments(identifiers='tests/identifiers.csv'))

        # This is an implicit assertion that the metadata has been written to
        # the correct place.
        with open('tests/metadata/sn88053082/1877/10/18/ed-1/seq-3') as f:
            metadata = json.load(f)

        self.assertEqual(list(metadata.keys()), [identifier])
        metadata = metadata[identifier]

        self.assertEqual(
            metadata['collections'],
            ["directory of us newspapers in american libraries"]
        )
        self.assertEqual(
            metadata['title'],
            "Delaware Tribune, and the Delaware State Journal (Wilmington, Del.) 1877-18??"
        )
        self.assertEqual(
            metadata['subjects'],
            [{"delaware": "https://www.loc.gov/search/?fa=subject:delaware&fo=json"}, {"new castle": "https://www.loc.gov/search/?fa=subject:new+castle&fo=json"}, {"newspapers": "https://www.loc.gov/search/?fa=subject:newspapers&fo=json"}, {"united states": "https://www.loc.gov/search/?fa=subject:united+states&fo=json"}, {"wilmington": "https://www.loc.gov/search/?fa=subject:wilmington&fo=json"}, {"wilmington (del.)": "https://www.loc.gov/search/?fa=subject:wilmington+%28del.%29&fo=json"}]
        )
        self.assertEqual(
            metadata['subject_headings'],
            ["Wilmington (Del.)--Newspapers", "Delaware--Wilmington", "United States--Delaware--New Castle--Wilmington"]
        )
        self.assertEqual(
            # Order is unimportant, and not guaranteed.
            set(metadata['locations']),
            set(["new castle", "delaware", "united states", "wilmington"])
        )
        self.assertEqual(
            metadata['description'],
            ["Weekly Began in 1877. Archived issues are available in digital format from the Library of Congress Chronicling America online collection. Description based on: Vol. 11, no. 544 (June 14, 1877). Delaware state journal (Wilmington, Del. : 1870) 2574-6766 (DLC)sn 84026836 (OCoLC)10718558"]
        )
        self.assertEqual(
            metadata['states'],
            ['Delaware']
        )
        self.assertEqual(
            metadata['date'],
            '1877-10-18'
        )
        self.assertEqual(
            metadata['url'],
            'https://chroniclingamerica.loc.gov/lccn/sn88053082/1877-10-18/ed-1/seq-3'
        )
        self.assertEqual(
            metadata['image_url'],
            None
        )

        shutil.rmtree('tests/metadata')

if __name__ == '__main__':
    unittest.main()

  # - outputs ChronAm to correct directory
  # - outputs items to correct directory
  # - does not fetch cached
  # - ChronAm file has expected contents
  # - item file has expected contents
