import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import spacy

from web_knowledge import (
    VENWebKnowledge,
    WebAnswer,
    WebLookupError,
    _SearchResultsParser,
)


class WebKnowledgeTests(unittest.TestCase):
    SEARCH_PAGE = """
    <rss version="2.0"><channel>
      <item>
        <title>What Is an Engineer? - Example</title>
        <link>https://example.org/engineer</link>
        <description>
        An engineer uses scientific knowledge to solve practical problems.
        </description>
      </item>
    </channel></rss>
    """

    def setUp(self):
        self.nlp = spacy.load("en_core_web_sm")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_file = Path(self.temp_dir.name) / "web_cache.json"
        self.knowledge = VENWebKnowledge(self.nlp, self.cache_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_recognizes_question_and_information_requests(self):
        self.assertTrue(
            self.knowledge.is_search_request("What is the capital of France?")
        )
        self.assertTrue(self.knowledge.is_search_request("Tell me about Mars."))
        self.assertFalse(
            self.knowledge.is_search_request("Birds are animals.")
        )

    def test_searches_public_web_results_and_returns_a_citation(self):
        with patch(
            "web_knowledge.urlopen",
            return_value=self.response(self.SEARCH_PAGE),
        ) as open_url:
            answer = self.knowledge.search("What is an engineer?")

        self.assertEqual(answer.title, "What Is an Engineer? - Example")
        self.assertIn("scientific knowledge", answer.text)
        self.assertEqual(answer.url, "https://example.org/engineer")
        self.assertIn("q=engineer", open_url.call_args.args[0].full_url)
        self.assertIn("format=rss", open_url.call_args.args[0].full_url)

    def test_reuses_and_persists_web_results_in_a_local_cache(self):
        with patch(
            "web_knowledge.urlopen",
            return_value=self.response(self.SEARCH_PAGE),
        ) as open_url:
            first = self.knowledge.search("What is an engineer?")
            second = self.knowledge.search("What is an engineer?")

        self.assertEqual(open_url.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(
            self.knowledge.load_cache()["public-web:engineer"]["title"],
            "What Is an Engineer? - Example",
        )

        restored = VENWebKnowledge(self.nlp, self.cache_file)
        with patch("web_knowledge.urlopen") as open_url:
            cached = restored.search("What is an engineer?")

        open_url.assert_not_called()
        self.assertEqual(cached, first)

    def test_prefers_results_matching_the_full_question(self):
        search_page = """
        <rss><channel>
          <item>
            <title>Capital punishment in France</title>
            <link>https://example.org/capital-punishment</link>
            <description>Capital punishment in France is banned.</description>
          </item>
          <item>
            <title>List of capitals of France</title>
            <link>https://example.org/capitals</link>
            <description>The capital of France has been Paris for centuries.</description>
          </item>
        </channel></rss>
        """
        with patch(
            "web_knowledge.urlopen",
            return_value=self.response(search_page),
        ):
            answer = self.knowledge.search(
                "What is the capital of France?"
            )

        self.assertEqual(answer.title, "List of capitals of France")
        self.assertIn("Paris", answer.text)

    def test_rejects_capital_punishment_results_for_capital_city_queries(self):
        irrelevant = {
            "title": "Capital punishment in France",
            "excerpt": "Capital punishment in France is banned.",
            "url": "https://example.org/capital-punishment",
        }
        relevant_answer = WebAnswer(
            title="List of capitals of France",
            text="The capital of France has been Paris for centuries.",
            url="https://en.wikipedia.org/wiki/List_of_capitals_of_France",
        )
        with (
            patch.object(
                self.knowledge,
                "request_results",
                return_value=[irrelevant],
            ),
            patch.object(
                self.knowledge,
                "request_json",
                return_value={
                    "Heading": "Capital punishment in France",
                    "AbstractText": "Capital punishment in France is banned.",
                    "AbstractURL": "https://example.org/capital-punishment",
                },
            ),
            patch.object(
                self.knowledge,
                "search_wikipedia",
                return_value=relevant_answer,
            ) as wikipedia,
        ):
            answer = self.knowledge.search("What is the capital of France?")

        wikipedia.assert_called_once_with("capital of france")
        self.assertEqual(answer, relevant_answer)

    def test_irrelevant_search_results_do_not_mask_a_relevant_fallback(self):
        relevant_answer = WebAnswer(
            title="Mars",
            text="Mars is a planet.",
            url="https://en.wikipedia.org/wiki/Mars",
        )
        with (
            patch.object(
                self.knowledge,
                "request_results",
                return_value=[{
                    "title": "A different topic",
                    "excerpt": "This page discusses unrelated subjects.",
                    "url": "https://example.org/unrelated",
                }],
            ),
            patch.object(
                self.knowledge,
                "search_instant_answers",
                return_value=relevant_answer,
            ) as fallback,
        ):
            answer = self.knowledge.search("Tell me about Mars.")

        fallback.assert_called_once_with("mars")
        self.assertEqual(answer, relevant_answer)

    def test_rejects_non_public_or_unsafe_result_links(self):
        for url in (
            "http://127.0.0.1/admin",
            "http://localhost/",
            "file:///etc/passwd",
            "https://user:password@example.org/private",
        ):
            with self.subTest(url=url):
                self.assertEqual(
                    _SearchResultsParser.extract_result_url(url),
                    "",
                )

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

    @staticmethod
    def response(content):
        from io import BytesIO

        return BytesIO(content.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
