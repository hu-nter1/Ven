import json
import tempfile
import unittest
from pathlib import Path

from context_engine import VENContext
from knowledge_engine import VENKnowledge
from semantic_engine import VENSemanticEngine


class SemanticEngineTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = VENSemanticEngine()

    def interpret(self, sentence):
        result = self.engine.interpret(sentence)
        self.assertTrue(result["understood"], result)
        self.assertEqual(len(result["propositions"]), 1, result)
        return result["propositions"][0]

    def test_category_statement(self):
        proposition = self.interpret("Birds are animals.")
        self.assertEqual(proposition["subject"], "birds")
        self.assertEqual(proposition["relation"], "is_a")
        self.assertEqual(proposition["object"], "animals")

    def test_adjective_copula_becomes_property(self):
        proposition = self.interpret("John is intelligent.")
        self.assertEqual(proposition["relation"], "has_property")
        self.assertEqual(proposition["object"], "intelligent")

    def test_negation_and_modality_are_preserved(self):
        negative = self.interpret("John does not love Mary.")
        self.assertTrue(negative["negation"])
        self.assertEqual(negative["relation"], "love")

        ability = self.interpret("I can swim.")
        self.assertEqual(ability["modality"], "ability")

    def test_coordinated_actions_inherit_subject(self):
        result = self.engine.interpret(
            "The boy reads a book and writes a letter."
        )
        self.assertEqual(
            [
                (item["subject"], item["relation"], item["object"])
                for item in result["propositions"]
            ],
            [
                ("the boy", "read", "a book"),
                ("the boy", "write", "a letter")
            ]
        )

    def test_questions_do_not_produce_propositions(self):
        result = self.engine.interpret("Are birds animals")
        self.assertEqual(result["sentence_type"], "question")
        self.assertEqual(result["propositions"], [])


class ContextMemoryTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = VENSemanticEngine()

    def test_explicit_memory_deduplication_contradiction_and_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            memory_file = Path(directory) / "memory.json"
            context = VENContext(self.engine, memory_file)

            learned = context.process("Birds are animals.")
            self.assertEqual(learned["decision"], "new_information")
            self.assertEqual(context.facts[0]["origin"], "explicit")
            self.assertEqual(context.facts[0]["relation"], "is_a")

            question = context.process("Are birds animals")
            self.assertEqual(question["decision"], "question")
            self.assertEqual(len(context.facts), 1)

            repeated = context.process("Birds are animals.")
            self.assertEqual(repeated["decision"], "consistent")
            self.assertEqual(len(context.facts), 1)

            contradiction = context.process("Birds are not animals.")
            self.assertEqual(contradiction["decision"], "contradiction")

            with memory_file.open("r", encoding="utf-8") as file:
                persisted = json.load(file)
            self.assertEqual(persisted, context.facts)

            reloaded = VENContext(self.engine, memory_file)
            self.assertEqual(reloaded.facts, context.facts)

    def test_local_knowledge_answers_natural_questions_and_infers_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            context = VENContext(
                self.engine,
                Path(directory) / "memory.json"
            )
            knowledge = VENKnowledge(
                context.facts,
                self.engine.interpreter.nlp
            )

            context.process("Birds are animals.")
            context.process("Animals are living things.")
            context.process("An apple is food.")
            context.process("John is intelligent.")
            context.process("John does not love Mary.")

            self.assertIn("Birds are animals", knowledge.answer("Are birds animals?"))
            self.assertIn(
                "Animals are living things",
                knowledge.answer("Are birds living things?")
            )
            self.assertIn("Birds are animals", knowledge.answer("What are birds?"))
            self.assertIn("An apple is food", knowledge.answer("Is an apple food?"))
            self.assertIn(
                "John is intelligent",
                knowledge.answer("Is John intelligent?")
            )
            self.assertIn(
                "John does not love Mary",
                knowledge.answer("Does John love Mary?")
            )

    def test_common_facts_work_without_network_access(self):
        knowledge = VENKnowledge([], self.engine.interpreter.nlp)

        self.assertIn(
            "Earth is a planet",
            knowledge.answer("Is Earth a planet?")
        )
        self.assertIn(
            "Earth orbits the Sun",
            knowledge.answer("Does Earth orbit the Sun?")
        )
        self.assertIn(
            "Earth orbits the Sun",
            knowledge.answer("What does Earth orbit?")
        )
        self.assertIn(
            "Plants need sunlight",
            knowledge.answer("Do plants need sunlight?")
        )

    def test_unknown_question_is_not_learned_as_a_fact(self):
        with tempfile.TemporaryDirectory() as directory:
            context = VENContext(
                self.engine,
                Path(directory) / "memory.json"
            )
            knowledge = VENKnowledge(
                context.facts,
                self.engine.interpreter.nlp
            )

            result = context.process("Do birds fly?")
            self.assertEqual(result["decision"], "question")
            self.assertEqual(context.facts, [])
            self.assertIn("don't know", knowledge.answer("Do birds fly?"))


if __name__ == "__main__":
    unittest.main()
