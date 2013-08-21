# -*- coding: utf-8 -*-

"""
This is the testing suite for the models within the search module
"""

import json
from django.test import TestCase
from django.test.utils import override_settings
from pyfuzz.generator import random_regex, random_language

from search.models import _snippet_generator, _get_content_url, SearchResults
from test_mongo import dummy_document

TEST_TEXT = "Lorem ipsum dolor sit amet, consectetur adipisicing elit, \
            sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. \
            Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris \
            nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in \
            reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. \
            Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia \
            deserunt mollit anim id est laborum."

TEST_GREEK = u"Σο οι δεύτερον απόσταση απαγωγής ολόκληρο πω. Είχε γιου βάση όλα \
             νου στην όπου σούκ. Ανάλυσης νεόφερτο ας εκ νεανικής τεκμήρια νε θα \
             εξαιτίας δείχνουν. Τη αν ιι έν συμπαίκτης παράδειγμα υποτίθεται τελευταίες. \
             Μου στίχους σαν γίνεται χιούμορ πως αρχίζει κατ σφυγμός συνθήκη. Αναγνώστη \
             προτιμούν σύγχρονες τη κι να κινήματος. Φίλτρο στήθος πει ατο κεί τέλους. \
             Χωρική θέσεις δε χτένας ίμερας έρευνα έμμεση αρ. Προκύψει επίλογοι ιππασίας σαν."

def dummy_entry(score):
    """
    This creates a fully-fledged fake response entry for a given score
    """

    id_ = dummy_document("id", ["tag", "org", "course", "category", "name"], "regex", regex="[a-zA-Z0-9]", length=25)
    source = dummy_document("_source", ["thumbnail", "searchable_text"], "regex", regex="[a-zA-Z0-9]", length=50)
    string_id = json.dumps(id_["id"])
    source["_source"].update({"id": string_id, "course_id": random_regex(regex="[a-zA-Z0-9/]", length=50)})
    document = {"_score": score}
    source.update(document)
    return source


class FakeResponse():
    """
    Fake minimal response, just wrapping a given dictionary in a response-like object
    """

    def __init__(self, dictionary):
        self.content = json.dumps(dictionary)


class ModelTest(TestCase):
    """
    Tests SearchResults and SearchResult models as well as associated helper functions
    """

    @override_settings(SENTENCE_TOKENIZER="tokenizers/punkt/english.pickle")
    def test_snippet_generation(self):
        snippets = _snippet_generator(TEST_TEXT, "quis nostrud")
        self.assertTrue(snippets.startswith("Ut enim ad minim"))
        self.assertTrue(snippets.strip().endswith("anim id est laborum."))

    @override_settings(SENTENCE_TOKENIZER="DETECT")
    def test_language_detection(self):
        snippets = _snippet_generator(TEST_GREEK, u"νου στην όπου")
        self.assertTrue(snippets.startswith(u"Είχε γιου"))

    @override_settings(SENTENCE_TOKENIZER="tokenizers/punkt/english.pickle")
    def test_highlighting(self):
        highlights = _snippet_generator(TEST_TEXT, "quis nostrud")
        self.assertTrue(highlights.startswith("Ut enim ad minim"))
        self.assertTrue(highlights.strip().endswith("anim id est laborum."))
        self.assertTrue('<b class="highlight">quis</b>' in highlights)
        self.assertTrue('<b class="highlight">nostrud</b>' in highlights)

    @override_settings(SENTENCE_TOKENIZER="tokenizers/punkt/english.pickle")
    def test_search_result(self):
        scores = [1.0, 5.2, 2.0, 123.2]
        hits = [dummy_entry(score) for score in scores]
        full_return = FakeResponse({"hits": {"hits": hits}})
        results = SearchResults(full_return, s="fake query", sort="relevance")
        scores = [entry.score for entry in results.entries]
        self.assertEqual([123.2, 5.2, 2.0, 1.0], scores)

    def test_get_content_url(self):
        id_ = json.dumps({"org": "test-org", "course": "test-course"})
        document = {"id": id_}
        static_url = "/static/images/test/image/url.jpg"
        expected_content_url = "/c4x/test-org/test-course/asset/images_test_image_url.jpg"
        self.assertEqual(expected_content_url, _get_content_url(document, static_url))
