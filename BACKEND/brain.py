
import json
import re
from pathlib import Path

from response_engine import VENResponseEngine


class VENBrain:

    def __init__(self, response_engine=None):
        self.name = "VEN"
        self.response_engine = response_engine or VENResponseEngine()
        self.last_topic = None

        vocabulary_file = Path(__file__).parent / "vocabulary.json"

        with open(vocabulary_file, "r", encoding="utf-8") as file:
            words = json.load(file)

        self.vocabulary = {
            item["word"].lower(): item
            for item in words
            if isinstance(item, dict) and item.get("word")
        }

        print(f"VEN loaded {len(self.vocabulary)} words.")

        self.intents = {
            "greeting": [
                "hello", "hi", "hey",
                "good morning", "good afternoon",
                "good evening", "how are you",
                "how are you doing"
            ],
            "gratitude": [
                "thank you", "thanks", "many thanks"
            ],
            "farewell": [
                "bye", "goodbye", "see you",
                "see you later"
            ],
            "identity": [
                "your name", "what is your name",
                "who are you", "tell me about yourself"
            ],
            "help": [
                "help", "help me", "can you help me"
            ]
        }

        # Different ways people ask vocabulary questions.
        self.word_patterns = [
            (
                "example",
                r"(?:can|could) you give (?:me )?an example(?: of (.+))?",
            ),
            ("example", r"(?:give (?:me )?)?an example of (.+)"),
            ("example", r"(?:give (?:me )?)?an example"),
            ("example", r"use (.+) in a sentence"),
            ("example", r"show me an example of (.+)"),

            ("synonyms", r"synonyms of (.+)"),
            ("synonyms", r"synonyms for (.+)"),
            ("synonyms", r"another word for (.+)"),
            ("synonyms", r"words that mean the same as (.+)"),
            ("synonyms", r"words similar to (.+)"),
            ("synonyms", r"similar words to (.+)"),

            ("antonyms", r"antonyms of (.+)"),
            ("antonyms", r"antonyms for (.+)"),
            ("antonyms", r"opposite of (.+)"),
            ("antonyms", r"opposite word for (.+)"),
            ("antonyms", r"what is the opposite of (.+)"),

            ("related", r"related words of (.+)"),
            ("related", r"words related to (.+)"),
            ("related", r"words associated with (.+)"),

            ("meaning", r"what does (.+) mean"),
            ("meaning", r"what is the meaning of (.+)"),
            ("meaning", r"meaning of (.+)"),
            ("meaning", r"define (.+)"),
            ("meaning", r"explain the meaning of (.+)"),
            ("meaning", r"explain what (.+) means"),
            ("meaning", r"can you explain what (.+) means"),
            ("meaning", r"tell me what (.+) means"),
            ("meaning", r"what is (.+)"),
        ]

    def normalize(self, message):
        message = message.lower().strip()
        message = re.sub(r"[^a-z0-9\s']", "", message)
        message = re.sub(r"\s+", " ", message)
        return message

    def contains_phrase(self, message, phrase):
        pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
        return re.search(pattern, message) is not None

    def explain_word(self, word, request_type):

        data = self.vocabulary.get(word)

        if not data:
            return None

        if request_type == "example":
            example = data.get("example")

            if example:
                sentence = str(example).strip()
                return self.response_engine.choose_response(
                    f"example:{word}",
                    [
                        f"For example: {sentence}",
                        f"Here's {word} in a sentence: {sentence}",
                        f"You could say: {sentence}",
                    ],
                )
            return self.generate_example(word, data)

        if request_type == "synonyms":
            synonyms = data.get("synonyms", [])

            if synonyms:
                return f"Synonyms of {word}: {', '.join(synonyms)}"

            return f"I don't have synonyms recorded for {word} yet."

        if request_type == "antonyms":
            antonyms = data.get("antonyms", [])

            if antonyms:
                return f"Antonyms of {word}: {', '.join(antonyms)}"

            return f"I don't have antonyms recorded for {word} yet."

        if request_type == "related":
            related = data.get("related_words", [])

            if related:
                return f"Words related to {word}: {', '.join(related)}"

            return f"I don't have related words recorded for {word} yet."

        meaning = data.get("meaning", "Meaning not available.")
        word_type = data.get("type", "unknown")
        self.last_topic = word
        return self.response_engine.choose_response(
            f"meaning:{word}",
            [
                f"As a {word_type}, {word} means {meaning}.",
                f"{word.capitalize()} is a {word_type}: {meaning}.",
                f"In this sense, {word} refers to {meaning}.",
            ],
        )

    def generate_example(self, word, data):
        word_type = data.get("type", "word")
        meaning = data.get("meaning", "").strip().rstrip(".")

        if word_type == "noun" and meaning:
            person_definition = re.match(
                r"^(?:a|an) person who (.+)$",
                meaning,
                re.IGNORECASE,
            )
            if person_definition:
                article = "An" if word[:1].lower() in "aeiou" else "A"
                example = (
                    f"{article} {word} {person_definition.group(1)}."
                )
            else:
                article = "An" if word[:1].lower() in "aeiou" else "A"
                example = f"{article} {word} is {meaning}."
        elif word_type == "verb":
            example = f"They {word} every day."
        elif word_type == "adjective":
            example = f"The {word} choice made sense."
        else:
            example = f"The word {word} appeared in the sentence."

        sentence_example = example[:1].lower() + example[1:]
        return self.response_engine.choose_response(
            f"example:{word}",
            [
                f"Here's an example of {word}: {example}",
                f"You could use {word} like this: {example}",
                f"For instance, {sentence_example}",
            ],
        )

    def think(self, message):

        message = self.normalize(message)

        if not message:
            return "You haven't said anything yet."

        for request_type, pattern in self.word_patterns:
            match = re.fullmatch(pattern, message)
            if not match:
                continue
            captured_word = match.group(1) if match.lastindex else None
            word = (captured_word or self.last_topic or "").strip()
            word = re.sub(r"^(the|a|an)\s+", "", word)
            if not word:
                if request_type == "example":
                    return self.response_engine.respond_to_missing_example_topic()
                return None

            response = self.explain_word(word, request_type)
            if response is not None:
                self.last_topic = word
            return response

        # Recognize conversational intentions.
        for intent, phrases in self.intents.items():
            for phrase in phrases:
                if self.contains_phrase(message, phrase):
                    return self.respond(intent, message)

        # Look up a word entered directly.
        if message in self.vocabulary:
            self.last_topic = message
            return self.explain_word(message, "meaning")

        return None

    def respond(self, intent, message=""):
        return self.response_engine.respond_to_intent(intent, message)
