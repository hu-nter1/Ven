import unittest
from unittest.mock import patch

from main import ChatRequest, ChatResponse, chat


class ChatRoutingTests(unittest.TestCase):
    def test_composes_a_reply_for_a_parsed_personal_statement(self):
        result = {
            "decision": "new_information",
            "meaning": {
                "propositions": [{
                    "subject": "i",
                    "relation": "has_property",
                    "object": "cool",
                    "negation": False,
                }]
            },
        }
        with (
            patch("main.ven_brain.think", return_value=None),
            patch("main.ven_context.process", return_value=result) as process,
            patch("main.ven_web_knowledge.is_search_request", return_value=False),
        ):
            response = chat(ChatRequest(message="am cool"))

        process.assert_called_once_with("I am cool")
        self.assertIn("cool", response.reply.lower())
        self.assertNotIn("still learning", response.reply.lower())

    def test_unknown_question_gets_an_honest_non_generic_reply(self):
        result = {"decision": "question"}
        with (
            patch("main.ven_brain.think", return_value=None),
            patch("main.ven_context.process", return_value=result),
            patch(
                "main.ven_knowledge.answer",
                return_value="I don't know that yet.",
            ),
            patch("main.search_web", return_value=None),
        ):
            response = chat(
                ChatRequest(message="What is an unlisted concept?")
            )

        self.assertIn("unlisted concept", response.reply.lower())
        self.assertNotIn("still learning", response.reply.lower())

    def test_web_answer_keeps_its_page_citation(self):
        result = {"decision": "question"}
        web_response = ChatResponse(
            reply="Here's a result from the web: a useful excerpt.",
            source_title="Example",
            source_url="https://example.org/article",
        )
        with (
            patch("main.ven_brain.think", return_value=None),
            patch("main.ven_context.process", return_value=result),
            patch(
                "main.ven_knowledge.answer",
                return_value="I don't know that yet.",
            ),
            patch("main.search_web", return_value=web_response),
        ):
            response = chat(ChatRequest(message="What is an obscure topic?"))

        self.assertEqual(response.source_title, "Example")
        self.assertEqual(response.source_url, "https://example.org/article")


if __name__ == "__main__":
    unittest.main()
