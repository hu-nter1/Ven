
from sentence_interpreter import SentenceInterpreter


class VENReasoning:

    def __init__(self):
        self.interpreter = SentenceInterpreter()
        self.facts = {}

    def process(self, sentence):

        meaning = self.interpreter.interpret(sentence)

        if not meaning["understood"]:
            return {
                "decision": "uncertain",
                "message": "I could not identify the sentence structure."
            }

        subject = meaning["subject"]
        action = meaning["action"]
        object_word = meaning["object"]
        negation = meaning["negation"]

        if not subject or not action:
            return {
                "decision": "incomplete",
                "message": "I need more information to understand this statement.",
                "meaning": meaning
            }

        # Create a representation of the relationship.
        fact_key = (
            subject.lower(),
            action.lower(),
            object_word.lower() if object_word else None
        )

        # True means the relationship is affirmed.
        truth_value = not negation

        # Check whether VEN has encountered this relationship.
        if fact_key in self.facts:

            previous_value = self.facts[fact_key]

            if previous_value != truth_value:
                return {
                    "decision": "contradiction",
                    "message": (
                        f"This conflicts with something I previously "
                        f"learned about {subject} and {action}."
                    ),
                    "meaning": meaning
                }

            return {
                "decision": "consistent",
                "message": "This agrees with information I already have.",
                "meaning": meaning
            }

        # Store a new relationship.
        self.facts[fact_key] = truth_value

        return {
            "decision": "new_information",
            "message": "I have learned a new relationship.",
            "meaning": meaning
        }


if __name__ == "__main__":

    ven = VENReasoning()

    conversations = [
        "John loves Mary.",
        "Mary loves John.",
        "John does not love Mary.",
        "John loves Mary."
    ]

    for sentence in conversations:

        result = ven.process(sentence)

        print("\nYOU:", sentence)
        print("VEN'S DECISION:", result["decision"])
        print("VEN:", result["message"])
