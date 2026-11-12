import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import spacy

from web_knowledge import VENWebKnowledge, WebLookupError


class WebKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_file = Path(self.temp_dir.name) / "web_cache.json"
        self.knowledge = VENWebKnowledge(self.nlp, self.cache_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def response(self, payload):
        return BytesIO(json.dumps(payload).encode("utf-8"))

    def test_recognizes_question_and_information_requests(self):
        self.assertTrue(
            self.knowledge.is_search_request("What is the capital of France?")
        )
        self.assertTrue(self.knowledge.is_search_request("Tell me about Mars."))
        self.assertFalse(
            self.knowledge.is_search_request("Birds are animals.")
        )

    def test_searches_clean_terms_and_prefers_a_direct_common_fact(self):
        search_results = {
            "pages": [
                {
                    "title": "Capital punishment in France",
                    "excerpt": "Capital punishment in France is banned.",
                },
                {
                    "title": "List of capitals of France",
                    "excerpt": (
                        "The capital of France has been Paris since 1944."
                    ),
                },
            ]
        }

        with patch(
            "web_knowledge.urlopen",
            return_value=self.response(search_results),
        ) as open_url:
            answer = self.knowledge.search(
                "What is the capital of France?"
            )

        self.assertEqual(answer.title, "List of capitals of France")
        self.assertIn("Paris", answer.text)
        self.assertEqual(
            answer.url,
            "https://en.wikipedia.org/wiki/List_of_capitals_of_France"
        )
        self.assertIn("q=capital+france", open_url.call_args.args[0].full_url)

    def test_reuses_and_persists_web_results_in_a_local_cache(self):
        search_results = {
            "pages": [
                {
                    "title": "Albert Einstein",
                    "excerpt": (
                        "<span class=\"searchmatch\">Albert</span> Einstein "
                        "was a theoretical physicist."
                    ),
                }
            ]
        }

        with patch(
            "web_knowledge.urlopen",
            return_value=self.response(search_results),
        ) as open_url:
            first = self.knowledge.search("Who was Albert Einstein?")
            second = self.knowledge.search("Who was Albert Einstein?")

        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(
            self.knowledge.load_cache()["albert einstein"]["title"],
            "Albert Einstein",
        )

        restored = VENWebKnowledge(self.nlp, self.cache_file)
        with patch("web_knowledge.urlopen") as open_url:
            cached = restored.search("Who was Albert Einstein?")

        open_url.assert_not_called()
        self.assertEqual(cached, first)

    def test_removes_spaces_before_punctuation_in_excerpts(self):
        answer = self.knowledge.clean_excerpt(
            "France is a country <span>.</span>"
        )

        self.assertEqual(answer, "France is a country.")

    def test_normalizes_punctuation_in_cached_excerpts(self):
        self.knowledge.cache["france"] = {
            "title": "France",
            "text": "France .",
            "url": "https://en.wikipedia.org/wiki/France",
            "expires_at": 9999999999,
        }

        answer = self.knowledge.get_cached_answer("france")

        self.assertEqual(answer.text, "France.")

    def test_does_not_send_personal_location_questions_to_the_web(self):
        for question in (
            "What is my home address?",
            "Can you tell me where I live?",
        ):
            with self.subTest(question=question), patch(
                "web_knowledge.urlopen"
            ) as open_url:
                answer = self.knowledge.search(question)

                self.assertIsNone(answer)
                open_url.assert_not_called()

    def test_reports_network_failures(self):
        with patch(
            "web_knowledge.urlopen",
            side_effect=URLError("offline"),
        ):
            with self.assertRaises(WebLookupError):
                self.knowledge.search("Who was Albert Einstein?")


if __name__ == "__main__":
    unittest.main()
