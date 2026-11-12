
from sentence_interpreter import SentenceInterpreter


class VENReference:

    def __init__(self):

        self.interpreter = SentenceInterpreter()

        self.people = {
            "he": None,
            "she": None,
            "they": None,
            "it": None
        }

    def process(self, sentence):

        meaning = self.interpreter.interpret(sentence)

        if not meaning["understood"]:
            return meaning

        subject = meaning["subject"]

        if not subject:
            return meaning

        subject_lower = subject.lower()

        # Resolve known pronouns.
        if subject_lower in self.people:

            previous_person = self.people[subject_lower]

            if previous_person:
                meaning["original_subject"] = subject
                meaning["subject"] = previous_person

            else:
                meaning["reference_warning"] = (
                    "I do not know who this pronoun refers to."
                )

            return meaning

        # Remember the most recently mentioned person.
        # Do not assign gender automatically.
        self.people["they"] = subject

        return meaning


if __name__ == "__main__":

    ven = VENReference()

    # For this controlled experiment, provide known references.
    ven.people["he"] = "John"
    ven.people["she"] = "Mary"

    tests = [
        "John loves Mary.",
        "He likes football.",
        "Mary studies mathematics.",
        "She enjoys reading."
    ]

    for sentence in tests:

        result = ven.process(sentence)

        print("\nYOU:", sentence)
        print("VEN IDENTIFIES:", result)

    print("\nVEN'S PEOPLE:")
    print(ven.people)
