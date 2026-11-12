
import json
import re
from pathlib import Path


class VENBrain:

    def __init__(self):
        self.name = "VEN"

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
            ("example", r"example of (.+)"),
            ("example", r"give me an example of (.+)"),
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
            ("meaning", r"what is (.+)")
        ]

    def normalize(self, message):
        message = message.lower().strip()
        message = re.sub(r"[^a-z0-9\s']", "", message)
        message = re.sub(r"\s+", " ", message)
        return message

    def contains_phrase(self, message, phrase):
        pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
        return re.search(pattern, message) is not None

    def find_word_request(self, message):

        for request_type, pattern in self.word_patterns:
            match = re.fullmatch(pattern, message)

            if match:
                word = match.group(1).strip()

                # Remove common unnecessary words at the beginning.
                word = re.sub(
                    r"^(the|a|an)\s+",
                    "",
                    word
                )

                return word, request_type

        return None, None

    def explain_word(self, word, request_type):

        data = self.vocabulary.get(word)

        if not data:
            return (
                f"I don't have the word '{word}' in my vocabulary yet. "
                "I am still learning."
            )

        if request_type == "example":
            example = data.get("example")

            if example:
                return f"Example of {word}: {example}"

            return (
                f"I know the meaning of {word}, "
                "but I don't have an example sentence yet."
            )

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

        return (
            f"{word.capitalize()} is a {word_type}. "
            f"{meaning}"
        )

    def think(self, message):

        message = self.normalize(message)

        if not message:
            return "You haven't said anything yet."

        # Recognize conversational intentions.
        for intent, phrases in self.intents.items():
            for phrase in phrases:
                if self.contains_phrase(message, phrase):
                    return self.respond(intent)

        # Recognize different vocabulary question formats.
        word, request_type = self.find_word_request(message)

        if word:
            return self.explain_word(word, request_type)

        # Look up a word entered directly.
        if message in self.vocabulary:
            return self.explain_word(message, "meaning")

        return (
            "I am still learning. I don't understand that yet. "
            "You can teach me by helping me learn new words and questions."
        )

    def respond(self, intent):

        responses = {
            "greeting": "Hello! It is nice to talk with you.",
            "gratitude": "You are welcome!",
            "farewell": "Goodbye! Talk to you later.",
            "identity": "My name is VEN. I am your personal AI assistant.",
            "help": "Of course. Tell me what you need help with."
        }

        return responses.get(intent, "I am still learning.")
