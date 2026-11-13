import unittest
from unittest.mock import patch

from main import (
    ChatRequest,
    ChatResponse,
    chat,
    forget_memory,
    read_memory,
    ven_brain,
    ven_context,
)


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
            patch("main.ven_brain.think", return_value=None) as think,
            patch("main.ven_context.process", return_value=result) as process,
            patch("main.ven_web_knowledge.is_search_request", return_value=False),
        ):
            response = chat(ChatRequest(message="am cool", local_hour=10))

        think.assert_called_once_with("am cool", 10, [])
        process.assert_called_once_with("I am cool")
        self.assertIn("cool", response.reply.lower())
        self.assertNotIn("still learning", response.reply.lower())

    def test_repeat_question_uses_history_without_searching_the_web(self):
        history = [
            {"role": "assistant", "content": "The answer is 42."},
        ]
        with (
            patch("main.ven_brain.think", return_value='I said: “The answer is 42.”') as think,
            patch("main.ven_context.process") as process,
            patch("main.search_web") as search,
        ):
            response = chat(
                ChatRequest(
                    message="What did you say?",
                    conversation_history=history,
                )
            )

        self.assertIn("The answer is 42.", response.reply)
        think.assert_called_once_with("What did you say?", None, history)
        process.assert_not_called()
        search.assert_not_called()

    def test_typo_correction_happens_before_statement_interpretation(self):
        result = {
            "decision": "new_information",
            "meaning": {
                "propositions": [{
                    "subject": "i",
                    "relation": "has_property",
                    "object": "okay",
                    "negation": True,
                }]
            },
        }
        with (
            patch("main.ven_brain.think", return_value=None),
            patch("main.ven_context.process", return_value=result) as process,
            patch("main.ven_web_knowledge.is_search_request", return_value=False),
        ):
            chat(ChatRequest(message="I am nt oky"))

        process.assert_called_once_with("I am not okay")

    def test_affirmative_answer_to_assistant_question_stays_in_chat(self):
        with (
            patch("main.ven_context.process") as process,
            patch("main.search_web") as search,
            patch(
                "main.ven_brain.response_engine.choose_response",
                side_effect=lambda _key, choices: choices[0],
            ),
        ):
            response = chat(
                ChatRequest(
                    message="yes",
                    conversation_history=[
                        {
                            "role": "assistant",
                            "content": "Anything you'd like to dive into?",
                        }
                    ],
                )
            )

        self.assertNotIn("affirmative", response.reply.lower())
        self.assertNotIn("noun", response.reply.lower())
        process.assert_not_called()
        search.assert_not_called()

    def test_new_conversation_resets_the_vocabulary_followup_topic(self):
        def verify_reset(*_args):
            self.assertIsNone(ven_brain.last_topic)
            return "Hello!"

        with (
            patch.object(ven_brain, "last_topic", "engineer"),
            patch("main.ven_brain.think", side_effect=verify_reset),
        ):
            response = chat(
                ChatRequest(
                    message="Hello",
                    new_conversation=True,
                )
            )

        self.assertEqual(response.reply, "Hello!")

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

    def test_memory_endpoint_lists_learned_facts(self):
        facts = [{"subject": "i", "relation": "has_property", "object": "calm"}]
        with patch.object(ven_context, "facts", facts):
            self.assertEqual(read_memory(), {"facts": facts})

    def test_memory_endpoint_can_forget_a_selected_fact(self):
        facts = [
            {"subject": "i", "relation": "has_property", "object": "calm"},
            {"subject": "i", "relation": "likes", "object": "music"},
        ]
        with (
            patch.object(ven_context, "facts", facts),
            patch.object(ven_context, "save_memory") as save_memory,
        ):
            result = forget_memory(0)

        self.assertEqual(len(result["facts"]), 1)
        self.assertEqual(result["facts"][0]["object"], "music")
        save_memory.assert_called_once_with()

    def test_memory_endpoint_rejects_an_invalid_fact_index(self):
        with patch.object(ven_context, "facts", []):
            with self.assertRaises(Exception) as error:
                forget_memory(0)

        self.assertEqual(getattr(error.exception, "status_code", None), 404)


if __name__ == "__main__":
    unittest.main()
