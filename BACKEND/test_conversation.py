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
        self.assertIn("How are you doing", third)

    def test_greetings_have_many_combinations_at_every_time_of_day(self):
        option_counts = []
        engine = VENResponseEngine(
            choose=lambda choices: (
                option_counts.append(len(choices)),
                choices[0],
            )[1]
        )

        for hour in (7, 13, 18, 23):
            with self.subTest(hour=hour):
                reply = engine.respond_to_intent(
                    "greeting",
                    "Hello",
                    local_hour=hour,
                )
                self.assertTrue(reply.startswith(engine.greeting_context(hour)[0]))

        self.assertTrue(all(count >= 80 for count in option_counts))

    def test_repeat_and_clarification_followups_use_conversation_history(self):
        history = [
            {"role": "user", "content": "Who is Ada Lovelace?"},
            {"role": "assistant", "content": "Ada Lovelace was a mathematician."},
        ]

        repeated = self.brain.think(
            "What did you say?",
            conversation_history=history,
        )
        clarified = self.brain.think(
            "What do you mean?",
            conversation_history=history,
        )
        without_history = self.brain.think("What did you say?")

        self.assertIn("Ada Lovelace was a mathematician.", repeated)
        self.assertIn("Ada Lovelace was a mathematician.", clarified)
        self.assertIn("haven't replied", without_history)

    def test_affirmative_reply_continues_the_previous_question(self):
        prompt = (
            "Good morning! Great to chat with you this morning. "
            "Anything you'd like to dive into?"
        )

        reply = self.brain.think(
            "yes",
            conversation_history=[
                {"role": "assistant", "content": prompt},
            ],
        )

        self.assertTrue(
            any(phrase in reply.lower() for phrase in ("what", "where"))
        )
        self.assertNotIn("affirmative", reply.lower())

    def test_standalone_affirmation_is_not_defined_as_a_word(self):
        reply = self.brain.think("yes")

        self.assertNotIn("noun", reply.lower())
        self.assertNotIn("affirmative", reply.lower())
        self.assertIn("what", reply.lower())

    def test_corrects_high_confidence_spelling_errors_before_interpretation(self):
        self.assertEqual(
            self.brain.correct_message("I am nt oky"),
            "I am not okay",
        )
        self.assertEqual(
            self.brain.correct_message("That is a quikc test"),
            "That is a quick test",
        )

        corrected = self.brain.correct_message("I am nt oky")
        with tempfile.TemporaryDirectory() as directory:
            context = VENContext(
                VENSemanticEngine(),
                Path(directory) / "memory.json",
            )
            result = context.process(corrected)

        reply = self.brain.response_engine.respond_to_statement(
            corrected,
            result,
        )
        self.assertIn("not feeling okay", reply.lower())

    def test_greetings_use_the_phone_local_time_of_day(self):
        expected = {
            7: "Good morning!",
            13: "Good afternoon!",
            18: "Good evening!",
            23: "Hello!",
            2: "Hello!",
        }
        for hour, salutation in expected.items():
            with self.subTest(hour=hour):
                reply = self.brain.think("Hello", local_hour=hour)
                self.assertTrue(reply.startswith(salutation))
                if hour in (23, 2):
                    self.assertIn("night", reply)

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
