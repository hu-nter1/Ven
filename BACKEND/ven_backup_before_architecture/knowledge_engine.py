
import json
import re
import spacy
from pathlib import Path


class VENKnowledge:

    def __init__(self):

        self.nlp = spacy.load("en_core_web_sm")

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

    def normalize(self, word):

        return self.nlp(word)[0].lemma_.lower()

    # Convert verbs into their present-tense form for he/she/it.
    def conjugate(self, verb):

        if verb.endswith("y") and len(verb) > 1:
            if verb[-2] not in "aeiou":
                return verb[:-1] + "ies"

        if verb.endswith(("s", "sh", "ch", "x", "z", "o")):
            return verb + "es"

        return verb + "s"

    def answer(self, question):

        question = question.strip().rstrip("?").lower()

        # Questions asking what someone does.
        what_match = re.fullmatch(
            r"what does (.+?) ([a-z]+)",
            question
        )

        if what_match:

            subject = what_match.group(1)
            action = self.normalize(what_match.group(2))

            for fact in reversed(self.facts):

                if (
                    fact["subject"] == subject
                    and fact["action"] == action
                    and fact["object"]
                    and not fact["negation"]
                ):

                    verb = self.conjugate(action)

                    return (
                        f"{subject.capitalize()} "
                        f"{verb} {fact['object']}."
                    )

            return "I do not have that information in my memory."

        # Questions asking who receives an action.
        who_match = re.fullmatch(
            r"who does (.+?) ([a-z]+)",
            question
        )

        if who_match:

            subject = who_match.group(1)
            action = self.normalize(who_match.group(2))

            for fact in reversed(self.facts):

                if (
                    fact["subject"] == subject
                    and fact["action"] == action
                    and fact["object"]
                    and not fact["negation"]
                ):

                    return fact["object"].capitalize() + "."

            return "I do not have that information in my memory."

        return "I do not understand that question yet."


if __name__ == "__main__":

    ven = VENKnowledge()

    questions = [
        "What does John like?",
        "Who does John love?",
        "What does Mary study?",
        "What does Mary enjoy?"
    ]

    for question in questions:

        print("\nYOU:", question)
        print("VEN:", ven.answer(question))
