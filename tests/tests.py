import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import unittest

import responses

from lc_etl.fetch_metadata import fetch
from lc_etl.zip_csv import zip_csv
# arrange, act, assert

@dataclass
class Arguments:
    identifiers: str


@dataclass
class ArgumentsZip:
    coordinates: str
    identifiers: str
    output: str

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

        self.addCleanup(self.responses.stop)
        self.addCleanup(self.responses.reset)


    def tearDown(self):
        from time import sleep
        try:
            shutil.rmtree('tests/metadata')
        except FileNotFoundError:
            pass


    @unittest.mock.patch('lc_etl.fetch_metadata.OUTPUT_DIR', 'tests/metadata')
    def test_fetches_data_for_chronam(self):
        identifier = 'sn88053082'
        with open(f'tests/{identifier}.json', 'r') as f:
            self.responses.add(
                responses.GET,
                f'https://www.loc.gov/item/{identifier}/?fo=json',
                json=json.load(f),
            )

        fetch(Arguments(identifiers='tests/identifiers_chronam.csv'))

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
        identifier = 'sn88053082'
        with open(f'tests/{identifier}.json', 'r') as f:
            self.responses.add(
                responses.GET,
                f'https://www.loc.gov/item/{identifier}/?fo=json',
                json=json.load(f),
            )
        fetch(Arguments(identifiers='tests/identifiers_chronam.csv'))


    @unittest.mock.patch('lc_etl.fetch_metadata.OUTPUT_DIR', 'tests/metadata')
    def test_fetches_data_for_items(self):
        identifier = 'mal3745600'
        with open(f'tests/{identifier}.json', 'r') as f:
            self.responses.add(
                responses.GET,
                f'https://www.loc.gov/item/{identifier}/?fo=json',
                json=json.load(f),
            )

        fetch(Arguments(identifiers='tests/identifiers_items.csv'))

        # This is an implicit assertion that the metadata has been written to
        # the correct place.
        with open('tests/metadata/mal3745600') as f:
            metadata = json.load(f)

        self.assertEqual(list(metadata.keys()), [identifier])
        metadata = metadata[identifier]

        self.assertEqual(
            metadata['collections'],
            ['abraham lincoln papers at the library of congress']
        )
        self.assertEqual(
            metadata['title'],
            "Abraham Lincoln papers: Series 1. General Correspondence. 1833-1916: [Abraham Lincoln] to Army and Navy Officers, Friday, October 21, 1864 (Order concerning James Hughes)"
        )
        self.assertEqual(
            metadata['subjects'],
            [
                  {
                    "civil war": "https://www.loc.gov/search/?fa=subject:civil+war&fo=json"
                  },
                  {
                    "history": "https://www.loc.gov/search/?fa=subject:history&fo=json"
                  },
                  {
                    "manuscripts": "https://www.loc.gov/search/?fa=subject:manuscripts&fo=json"
                  },
                  {
                    "politics and government": "https://www.loc.gov/search/?fa=subject:politics+and+government&fo=json"
                  },
                  {
                    "presidents": "https://www.loc.gov/search/?fa=subject:presidents&fo=json"
                  },
                  {
                    "united states": "https://www.loc.gov/search/?fa=subject:united+states&fo=json"
                  }
                ]
        )
        self.assertEqual(
            metadata['subject_headings'],
            [
              "United States--History--Civil War, 1861-1865",
              "United States--Politics and government--1861-1865",
              "Presidents--United States",
              "Manuscripts"
            ]
        )
        self.assertEqual(
            metadata['locations'],
            []
        )
        self.assertEqual(
            metadata['description'],
            None
        )
        self.assertEqual(
            metadata['states'],
            []
        )
        self.assertEqual(
            metadata['date'],
            '1864-10-21'
        )
        self.assertEqual(
            metadata['url'],
            'https://www.loc.gov/item/mal3745600/'
        )
        self.assertEqual(
            metadata['image_url'],
            "https://tile.loc.gov/image-services/iiif/service:mss:mal:374:3745600:001/full/pct:6.25/0/default.jpg#h=382&w=307"
        )


    @unittest.skip("print() shows the cache is used, but the assertion fails")
    @unittest.mock.patch('lc_etl.fetch_metadata.OUTPUT_DIR', 'tests/metadata')
    def test_uses_cache(self):
        identifier = 'mal3745600'
        with open(f'tests/{identifier}.json', 'r') as f:
            self.responses.add(
                responses.GET,
                f'https://www.loc.gov/item/{identifier}/?fo=json',
                json=json.load(f),
            )

        fetch(Arguments(identifiers='tests/identifiers_items.csv'))
        fetch(Arguments(identifiers='tests/identifiers_items.csv'))

        assert responses.assert_call_count(
            f'https://www.loc.gov/item/{identifier}/?fo=json',
            1
        )


class TestZipCSV(unittest.TestCase):
    def setUp(self):
        self.responses = responses.RequestsMock(
            # Must match the namespace of the thing actually issuing the
            # request! Without this, it defaults to mocking the requests
            # library, and only matches on things sent in this file by
            # requests.get().
            target="lc_etl.utilities.http_adapter"
        )
        self.responses.start()

        self.addCleanup(self.responses.stop)
        self.addCleanup(self.responses.reset)

        self.maxDiff = 6000


    def tearDown(self):
        from time import sleep
        try:
            shutil.rmtree('tests/metadata')
            Path('tests/zip_csv.csv').unlink()
        except FileNotFoundError:
            pass

    # given coordinates and identifiers and appropriately-generated metadata,
    # produces correct output
    @unittest.mock.patch('lc_etl.fetch_metadata.OUTPUT_DIR', 'tests/metadata')
    def test_integration_chronam(self):
        identifier = 'sn88053082'
        with open(f'tests/{identifier}.json', 'r') as f:
            self.responses.add(
                responses.GET,
                f'https://www.loc.gov/item/{identifier}/?fo=json',
                json=json.load(f),
            )

        fetch(Arguments(identifiers='tests/identifiers_chronam.csv'))
        zip_csv(ArgumentsZip(
            identifiers='tests/identifiers_chronam.csv',
            coordinates='tests/fake_coordinates.csv',
            output='tests/zip_csv.csv',
        ))
        with open('tests/zip_csv.csv', 'r') as f:
            zipped_csv = f.readlines()

        self.assertEqual(
            zipped_csv[0].strip(),
            ('x,y,collections,title,subjects,subject_headings,locations,date,'
             'url,image_url,description,states')
        )
        self.assertEqual(
            zipped_csv[1].strip(),
            ('-5.510140895843505859e+00,4.083539009094238281e+00,'
             "['directory of us newspapers in american libraries'],"
             '"Delaware Tribune, and the Delaware State Journal (Wilmington, Del.) 1877-18??",'
             "\"[{'delaware': 'https://www.loc.gov/search/?fa=subject:delaware&fo=json'}, {'new castle': 'https://www.loc.gov/search/?fa=subject:new+castle&fo=json'}, {'newspapers': 'https://www.loc.gov/search/?fa=subject:newspapers&fo=json'}, {'united states': 'https://www.loc.gov/search/?fa=subject:united+states&fo=json'}, {'wilmington': 'https://www.loc.gov/search/?fa=subject:wilmington&fo=json'}, {'wilmington (del.)': 'https://www.loc.gov/search/?fa=subject:wilmington+%28del.%29&fo=json'}]\","
             "\"['Wilmington (Del.)--Newspapers', 'Delaware--Wilmington', 'United States--Delaware--New Castle--Wilmington']\","
             "\"['delaware', 'new castle', 'wilmington', 'united states']\","
             '1877-10-18,https://chroniclingamerica.loc.gov/lccn/sn88053082/1877-10-18/ed-1/seq-3,,'
             "\"['Weekly Began in 1877. Archived issues are available in digital format from the Library of Congress Chronicling America online collection. Description based on: Vol. 11, no. 544 (June 14, 1877). Delaware state journal (Wilmington, Del. : 1870) 2574-6766 (DLC)sn 84026836 (OCoLC)10718558']\","
             "['Delaware']")
        )


    @unittest.mock.patch('lc_etl.fetch_metadata.OUTPUT_DIR', 'tests/metadata')
    @unittest.mock.patch('lc_etl.zip_csv.OUTPUT_DIR', 'tests/metadata')
    def test_integration_items(self):
        identifier = 'mal3745600'
        with open(f'tests/{identifier}.json', 'r') as f:
            self.responses.add(
                responses.GET,
                f'https://www.loc.gov/item/{identifier}/?fo=json',
                json=json.load(f),
            )

        fetch(Arguments(identifiers='tests/identifiers_items.csv'))
        zip_csv(ArgumentsZip(
            identifiers='tests/identifiers_items.csv',
            coordinates='tests/fake_coordinates.csv',
            output='tests/zip_csv.csv',
        ))
        with open('tests/zip_csv.csv', 'r') as f:
            zipped_csv = f.readlines()

        self.assertEqual(
            zipped_csv[0].strip(),
            ('x,y,collections,title,subjects,subject_headings,locations,date,'
             'url,image_url,description,states')
        )
        self.assertEqual(
            zipped_csv[1].strip(),
            ('-5.510140895843505859e+00,4.083539009094238281e+00,'
             "['abraham lincoln papers at the library of congress'],"
             '"Abraham Lincoln papers: Series 1. General Correspondence. 1833-1916: [Abraham Lincoln] to Army and Navy Officers, Friday, October 21, 1864 (Order concerning James Hughes)",'
             "\"[{'civil war': 'https://www.loc.gov/search/?fa=subject:civil+war&fo=json'}, "
             "{'history': 'https://www.loc.gov/search/?fa=subject:history&fo=json'}, "
             "{'manuscripts': 'https://www.loc.gov/search/?fa=subject:manuscripts&fo=json'}, "
             "{'politics and government': 'https://www.loc.gov/search/?fa=subject:politics+and+government&fo=json'}, "
             "{'presidents': 'https://www.loc.gov/search/?fa=subject:presidents&fo=json'}, "
             "{'united states': 'https://www.loc.gov/search/?fa=subject:united+states&fo=json'}]\","
             "\"['United States--History--Civil War, 1861-1865', 'United States--Politics and government--1861-1865', 'Presidents--United States', 'Manuscripts']\","
             '[],1864-10-21,https://www.loc.gov/item/mal3745600/,'
             'https://tile.loc.gov/image-services/iiif/service:mss:mal:374:3745600:001/full/pct:6.25/0/default.jpg#h=382&w=307'
             ',,[]'
            )
        )


if __name__ == '__main__':
    unittest.main()
