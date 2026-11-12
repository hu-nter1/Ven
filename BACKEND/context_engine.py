
import json
from pathlib import Path

from semantic_engine import VENSemanticEngine


class VENContext:

    def __init__(self, semantic_engine=None, memory_file=None):
        self.semantic_engine = semantic_engine or VENSemanticEngine()
        self.memory_file = (
            Path(memory_file)
            if memory_file
            else Path(__file__).parent / "ven_memory.json"
        )

        self.facts = self.load_memory()

    def load_memory(self):

        if not self.memory_file.exists():
            return []

        with open(self.memory_file, "r", encoding="utf-8") as file:
            facts = json.load(file)

        if not isinstance(facts, list) or not all(
            isinstance(fact, dict) for fact in facts
        ):
            raise ValueError(
                f"Memory file must contain a JSON list of facts: "
                f"{self.memory_file}"
            )

        return facts

    def save_memory(self):

        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(
                self.facts,
                file,
                indent=4,
                ensure_ascii=False
            )

    def process(self, sentence):

        meaning = self.semantic_engine.interpret(sentence)

        if not meaning["understood"]:
            return {
                "decision": "uncertain",
                "message": "I could not understand the sentence structure."
            }

        if meaning.get("sentence_type") == "question":
            return {
                "decision": "question",
                "message": "This is a question, not a statement to remember.",
                "meaning": meaning
            }

        propositions = meaning.get("propositions", [])

        if not propositions:
            return {
                "decision": "incomplete",
                "message": "I need more information to understand this statement.",
                "meaning": meaning
            }

        additions = []
        found_contradiction = False

        for proposition in propositions:
            matching_fact = next(
                (
                    fact
                    for fact in self.facts + additions
                    if self.same_relationship(fact, proposition)
                ),
                None
            )

            if matching_fact is None:
                additions.append(proposition)
            elif self.get_negation(matching_fact) != proposition["negation"]:
                found_contradiction = True

        if additions:
            self.facts.extend(additions)
            self.save_memory()

        if found_contradiction:
            decision = "contradiction"
            message = (
                "This statement conflicts with information "
                "I previously received."
            )
        elif additions:
            decision = "new_information"
            message = "I have stored this information in my memory."
        else:
            decision = "consistent"
            message = "This agrees with information in my memory."

        return {
            "decision": decision,
            "message": message,
            "meaning": meaning
        }

    @staticmethod
    def get_relation(fact):
        return fact.get("relation", fact.get("action"))

    @staticmethod
    def get_negation(fact):
        return fact.get("negation", False)

    @classmethod
    def same_relationship(cls, first, second):
        first_subject = first.get("subject")
        first_object = first.get("object")
        second_object = second.get("object")

        return (
            first_subject == second.get("subject")
            and cls.get_relation(first) == cls.get_relation(second)
            and first_object == second_object
            and first.get("modality") == second.get("modality")
        )

    def show_memory(self):

        return self.facts


if __name__ == "__main__":

    ven = VENContext()

    tests = [
        "John loves Mary.",
        "He likes football.",
        "Mary studies mathematics.",
        "She enjoys reading."
    ]

    for sentence in tests:

        result = ven.process(sentence)

        print("\nYOU:", sentence)
        print("VEN'S DECISION:", result["decision"])
        print("VEN:", result["message"])
        print("VEN IDENTIFIES:", result.get("meaning"))

    print("\nVEN'S MEMORY:")
    print(ven.show_memory())
