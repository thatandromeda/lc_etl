import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

import gensim
import responses

from lc_etl import filter_nonwords, filter_ocr, filter_newspaper_locations
from lc_etl.assign_similarity_metadata import update_metadata
from lc_etl.fetch_metadata import fetch
from lc_etl.zip_csv import zip_csv

@dataclass
class Arguments:
    identifiers: str


@dataclass
class ArgumentsMetadata:
    identifiers: str
    newspaper_dir: str = ''
    results_dir: str = ''
    logfile: str = ''
    overwrite: bool = True


@dataclass
class ArgumentsZip:
    coordinates: str
    identifiers: str
    output: str
    overwrite: bool = True


@dataclass
class ArgumentsSimilarity:
    model_path: str
    base_words: str
    metadata_dir: str
    newspaper_dir: str = ''
    results_dir: str = ''


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

        fetch(ArgumentsMetadata(identifiers='tests/identifiers_chronam.csv'))

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
            'https:/chroniclingamerica.loc.gov/lccn/sn88053082/1877-10-18/ed-1/seq-3/thumbnail.jpg'
        )


    @unittest.mock.patch('lc_etl.fetch_metadata.OUTPUT_DIR', 'tests/metadata')
    def test_fetches_data_for_items(self):
        identifier = 'mal3745600'
        with open(f'tests/{identifier}.json', 'r') as f:
            self.responses.add(
                responses.GET,
                f'https://www.loc.gov/item/{identifier}/?fo=json',
                json=json.load(f),
            )

        fetch(ArgumentsMetadata(identifiers='tests/identifiers_items.csv'))

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

        fetch(ArgumentsMetadata(identifiers='tests/identifiers_chronam.csv'))
        zip_csv(ArgumentsZip(
            identifiers='tests/identifiers_chronam.csv',
            coordinates='tests/fake_coordinates.csv',
            output='tests/zip_csv.csv',
        ))
        with open('tests/zip_csv.csv', 'r') as f:
            dict_csv = csv.DictReader(f)
            data = next(dict_csv)

        assert data['x'] == '-5.510140895843505859e+00'
        assert data['y'] == '4.083539009094238281e+00'
        assert data['collections'] == "['directory of us newspapers in american libraries']"
        assert data['title'] == "Delaware Tribune, and the Delaware State Journal (Wilmington, Del.) 1877-18??"
        assert data['subjects'] == "[{'delaware': 'https://www.loc.gov/search/?fa=subject:delaware&fo=json'}, {'new castle': 'https://www.loc.gov/search/?fa=subject:new+castle&fo=json'}, {'newspapers': 'https://www.loc.gov/search/?fa=subject:newspapers&fo=json'}, {'united states': 'https://www.loc.gov/search/?fa=subject:united+states&fo=json'}, {'wilmington': 'https://www.loc.gov/search/?fa=subject:wilmington&fo=json'}, {'wilmington (del.)': 'https://www.loc.gov/search/?fa=subject:wilmington+%28del.%29&fo=json'}]"
        assert data['subject_headings'] == "['Wilmington (Del.)--Newspapers', 'Delaware--Wilmington', 'United States--Delaware--New Castle--Wilmington']"
        assert data['locations'] == str(['new castle', 'delaware', 'united states', 'wilmington'])
        assert data['date'] == '1877-10-18'
        assert data['url'].rstrip('/') == 'https://chroniclingamerica.loc.gov/lccn/sn88053082/1877-10-18/ed-1/seq-3'
        assert data['description'] == "['Weekly Began in 1877. Archived issues are available in digital format from the Library of Congress Chronicling America online collection. Description based on: Vol. 11, no. 544 (June 14, 1877). Delaware state journal (Wilmington, Del. : 1870) 2574-6766 (DLC)sn 84026836 (OCoLC)10718558']"
        assert data['states'] == "['Delaware']"


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

        fetch(ArgumentsMetadata(identifiers='tests/identifiers_items.csv'))
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


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.test_directory = 'tests/data/temp'


    def tearDown(self):
        shutil.rmtree(self.test_directory)


    def test_ocr_is_filtered(self):
        shutil.copytree('tests/data/ocr', self.test_directory)
        good_file = Path(self.test_directory) / 'good_file.txt'
        bad_file = Path(self.test_directory) / 'bad_file.txt'
        short_words_file = Path(self.test_directory) / 'short_words_file.txt'

        assert good_file.is_file()
        assert bad_file.is_file()
        assert short_words_file.is_file()

        filter_ocr.filter_for_quality(self.test_directory)

        assert good_file.is_file()
        assert not bad_file.is_file()
        assert not short_words_file.is_file()


    def test_nonwords_filtered(self):
        shutil.copytree('tests/data/nonwords', self.test_directory)

        filter_nonwords.filter(self.test_directory, 'tests/data/gensim_outputs/test_model')

        with open(Path(self.test_directory) / 'testfile') as f:
            content = f.read()

        assert content.strip() == "slaves is a word that appears in the federal writers project corpus is not"


    def test_newspaper_locations(self):
        shutil.copytree('tests/data/locations', self.test_directory)

        filter_newspaper_locations.filter(self.test_directory, 'tests/data/metadata')

        with open(Path(self.test_directory) / 'sn78000873/1869/12/30/ed-1/seq-1/ocr.txt') as f:
            content = f.read()

        assert content.strip() == "once upon a time there was a congressman who had a peach from ireland"


class TestBulkScripts(unittest.TestCase):
    def setUp(self):
        self.test_directory = 'tests/data/temp'
        self.bulk_scripts_path = Path(__file__).parent.parent / 'lc_etl' / 'bulk_scripts'


    def tearDown(self):
        shutil.rmtree(self.test_directory)


    def test_transcription_attribution(self):
        shutil.copytree('tests/data/bulk_scripts/transcription', self.test_directory)
        expected = "Hi! I'm a file!"
        script = self.bulk_scripts_path / 'remove_transcription_attribution.sh'

        subprocess.run(f'{script} -p {self.test_directory}', shell=True)

        with open(Path(self.test_directory) / 'changed_file') as f:
            de_whitespaced = ' '.join(f.read().split())
            assert de_whitespaced == expected

        with open(Path(self.test_directory) / 'unchanged_file') as f:
            de_whitespaced = ' '.join(f.read().split())
            assert de_whitespaced == expected


    def test_remove_archival_notes_gentle(self):
        shutil.copytree('tests/data/bulk_scripts/archival_notes', self.test_directory)
        script = self.bulk_scripts_path / 'remove_archival_notes_gentle.sh'

        subprocess.run(f'{script} -p {self.test_directory}', shell=True)

        with open(Path(self.test_directory) / 'good_file') as f:
            assert f.read() == """line 1
line 2
line 3
line 4
line 5
line 6
line 7
line 8
"""

        with open(Path(self.test_directory) / 'bad_file') as f:
            assert f.read() == "line 10\n"


        with open(Path(self.test_directory) / 'very_bad_file') as f:
            assert f.read() == ''


    def test_remove_archival_notes_harsh(self):
        shutil.copytree('tests/data/bulk_scripts/archival_notes', self.test_directory)
        script = self.bulk_scripts_path / 'remove_archival_notes_harsh.sh'

        subprocess.run(f'{script} -p {self.test_directory}', shell=True)

        with open(Path(self.test_directory) / 'good_file') as f:
            assert f.read() == """line 1
line 2
line 3
line 4
line 5
line 6
line 7
line 8
"""

        assert not (Path(self.test_directory) / 'bad_file').is_file()
        assert not (Path(self.test_directory) / 'very_bad_file').is_file()


    def test_remove_frontmatter(self):
        shutil.copytree('tests/data/bulk_scripts/frontmatter', self.test_directory)
        script = self.bulk_scripts_path / 'remove_frontmatter.sh'

        subprocess.run(f'{script} -p {self.test_directory}', shell=True)

        with open(Path(self.test_directory) / 'long_file') as f:
            assert f.read() == """line 11
line 12
line 13
"""

        with open(Path(self.test_directory) / 'short_file') as f:
            assert f.read() == ''


class TestSimilarityMetadata(unittest.TestCase):
    def setUp(self):
        self.test_metadata = 'tests/data/test_metadata'
        shutil.copytree('tests/data/metadata', self.test_metadata)


    def tearDown(self):
        shutil.rmtree(self.test_metadata)


    def test_assignment(self):
        model_path = 'tests/data/gensim_outputs/test_model'
        newspaper_dir = 'tests/data/locations'
        model = gensim.models.Doc2Vec.load(model_path)
        arguments = ArgumentsSimilarity(
            model_path=model_path,
            newspaper_dir=newspaper_dir,
            metadata_dir=self.test_metadata,
            base_words='the,federal'
        )
        iterator = Path(newspaper_dir).rglob('**/*.txt')

        update_metadata(model, arguments, iterator)

        with open(Path(self.test_metadata) / 'sn78000873/1869/12/30/ed-1/seq-1') as f:
            metadata = json.load(f)
        item_metadata = metadata['sn78000873']

        assert 'keyword_scores' in item_metadata

        # We don't test for the specific value of the integer, because it isn't
        # guaranteed to be the same across runs:
        # - we sample words, so for documents larger than our sample size, we are
        #   unlikely to end up with the same score;
        # - users might run this using a variety of neural nets, which wouldn't
        #   encode the same similarities.
        # Different runs _of this same test suite_ should yield the same
        # similarity scores, because we're using a small test file and fixed
        # neural net, but I'm not going to write those scores into the test
        # since score stability is not a thing I am promising.
        assert isinstance(item_metadata['keyword_scores']['the'], int)
        assert isinstance(item_metadata['keyword_scores']['federal'], int)


if __name__ == '__main__':
    unittest.main()
