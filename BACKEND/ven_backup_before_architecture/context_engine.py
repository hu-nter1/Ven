
from reference_engine import VENReference
import json
from pathlib import Path


class VENContext:

    def __init__(self):

        self.references = VENReference()

        # These are explicit associations for our test.
        # Later, VEN will learn references through conversation.
        self.references.people["he"] = "john"
        self.references.people["she"] = "mary"

        self.memory_file = Path(__file__).parent / "ven_memory.json"

        self.facts = self.load_memory()

    def load_memory(self):

        if not self.memory_file.exists():
            return []

        try:
            with open(self.memory_file, "r", encoding="utf-8") as file:
                return json.load(file)

        except (json.JSONDecodeError, OSError):
            return []

    def save_memory(self):

        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(
                self.facts,
                file,
                indent=4,
                ensure_ascii=False
            )

    def process(self, sentence):

        # First understand the sentence and resolve references.
        meaning = self.references.process(sentence)

        if not meaning["understood"]:
            return {
                "decision": "uncertain",
                "message": "I could not understand the sentence structure."
            }

        subject = meaning["subject"]
        action = meaning["action"]
        object_word = meaning["object"]
        negation = meaning["negation"]

        if not subject or not action:
            return {
                "decision": "incomplete",
                "message": "I need more information.",
                "meaning": meaning
            }

        # Create a normalized fact.
        fact = {
            "subject": subject.lower(),
            "action": action.lower(),
            "object": object_word.lower() if object_word else None,
            "negation": negation,
            "original_sentence": sentence
        }

        # Compare with existing memory.
        for previous in self.facts:

            same_relationship = (
                previous["subject"] == fact["subject"]
                and previous["action"] == fact["action"]
                and previous["object"] == fact["object"]
            )

            if same_relationship:

                if previous["negation"] != fact["negation"]:

                    return {
                        "decision": "contradiction",
                        "message": (
                            "This statement conflicts with "
                            "information I previously received."
                        ),
                        "meaning": meaning
                    }

                return {
                    "decision": "consistent",
                    "message": (
                        "This agrees with information in my memory."
                    ),
                    "meaning": meaning
                }

        # Store new information.
        self.facts.append(fact)
        self.save_memory()

        return {
            "decision": "new_information",
            "message": "I have stored this information in my memory.",
            "meaning": meaning
        }

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
