import tempfile
import unittest
from pathlib import Path

from brain import VENBrain
from context_engine import VENContext
from response_engine import VENResponseEngine
from semantic_engine import VENSemanticEngine


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.brain = VENBrain(
            response_engine=VENResponseEngine(choose=lambda choices: choices[0])
        )

    def test_greetings_have_variety_without_repeating_consecutively(self):
        first = self.brain.think("Hello")
        second = self.brain.think("Hello")
        third = self.brain.think("How are you?")

        self.assertNotEqual(first, second)
        self.assertIn("How are you doing?", third)

    def test_word_definition_and_follow_up_example_use_local_knowledge(self):
        definition = self.brain.think("What is an engineer?")
        examples = [
            self.brain.think("Give an example")
            for _ in range(3)
        ]

        self.assertIn("scientific knowledge", definition)
        self.assertTrue(all("engineer" in item.lower() for item in examples))
        self.assertTrue(
            all("solve practical problems" in item for item in examples)
        )
        self.assertTrue(
            all("For instance, An" not in item for item in examples)
        )
        self.assertTrue(
            all("still learning" not in item.lower() for item in examples)
        )

    def test_example_request_can_be_worded_as_a_question(self):
        self.brain.think("What is an engineer?")

        example = self.brain.think("Could you give me an example?")

        self.assertIn("engineer", example.lower())
        self.assertIn("scientific knowledge", example)

    def test_example_request_without_a_topic_asks_a_clarifying_question(self):
        reply = self.brain.think("Could you give me an example?")

        self.assertIn("example", reply.lower())
        self.assertNotIn("still learning", reply.lower())

    def test_personal_statements_get_a_contextual_reply(self):
        with tempfile.TemporaryDirectory() as directory:
            context = VENContext(
                VENSemanticEngine(),
                Path(directory) / "memory.json",
            )
            result = context.process("I am cool")

        reply = self.brain.response_engine.respond_to_statement(
            "I am cool",
            result,
        )

        self.assertIn("cool", reply.lower())
        self.assertIn("what", reply.lower())
        self.assertNotIn("still learning", reply.lower())

    def test_unknown_questions_are_acknowledged_without_generic_learning_fallback(self):
        reply = self.brain.response_engine.respond_to_unknown_question(
            "What is an unknown concept?"
        )

        self.assertIn("unknown concept", reply)
        self.assertNotIn("still learning", reply.lower())


if __name__ == "__main__":
    unittest.main()
