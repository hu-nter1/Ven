
import json
import re
from pathlib import Path

from spacy.lang.en.stop_words import STOP_WORDS

from response_engine import VENResponseEngine


class VENBrain:
    COMMON_SPELLING_FIXES = {
        "dont": "don't",
        "doesnt": "doesn't",
        "didnt": "didn't",
        "isnt": "isn't",
        "arent": "aren't",
        "wasnt": "wasn't",
        "werent": "weren't",
        "wont": "won't",
        "cant": "can't",
        "couldnt": "couldn't",
        "wouldnt": "wouldn't",
        "shouldnt": "shouldn't",
        "nt": "not",
        "oky": "okay",
        "teh": "the",
    }

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
        self.vocabulary_rank = {
            item["word"].lower(): index
            for index, item in enumerate(words)
            if isinstance(item, dict) and item.get("word")
        }
        self.words_by_length = {}
        for word in self.vocabulary:
            if word.isalpha() and len(word) >= 3:
                self.words_by_length.setdefault(len(word), []).append(word)

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

    @staticmethod
    def edit_distance(first, second, limit):
        if abs(len(first) - len(second)) > limit:
            return limit + 1

        previous_previous = None
        previous = list(range(len(second) + 1))
        for first_index, first_char in enumerate(first, start=1):
            current = [first_index]
            row_minimum = first_index
            for second_index, second_char in enumerate(second, start=1):
                distance = min(
                    current[second_index - 1] + 1,
                    previous[second_index] + 1,
                    previous[second_index - 1]
                    + (first_char != second_char),
                )
                if (
                    previous_previous is not None
                    and first_index > 1
                    and second_index > 1
                    and first_char == second[second_index - 2]
                    and first[first_index - 2] == second_char
                ):
                    distance = min(
                        distance,
                        previous_previous[second_index - 2] + 1,
                    )
                current.append(distance)
                row_minimum = min(row_minimum, distance)
            if row_minimum > limit:
                return limit + 1
            previous_previous, previous = previous, current

        return previous[-1]

    @staticmethod
    def preserve_case(original, replacement):
        if original.isupper():
            return replacement.upper()
        if original.istitle():
            return replacement.capitalize()
        return replacement

    def correct_word(self, word):
        normalized = word.lower()
        if normalized == "nt":
            return self.preserve_case(word, "not")
        if normalized in STOP_WORDS:
            return word
        if normalized in self.vocabulary:
            return word
        replacement = self.COMMON_SPELLING_FIXES.get(normalized)
        if replacement:
            return self.preserve_case(word, replacement)
        if not normalized.isalpha() or len(normalized) < 3:
            return word

        max_distance = 1 if len(normalized) <= 5 else 2
        candidates = []
        for length in range(
            max(3, len(normalized) - max_distance),
            len(normalized) + max_distance + 1,
        ):
            for candidate in self.words_by_length.get(length, ()):
                distance = self.edit_distance(
                    normalized,
                    candidate,
                    max_distance,
                )
                if distance <= max_distance:
                    candidates.append(
                        (distance, self.vocabulary_rank[candidate], candidate)
                    )
        if not candidates:
            return word

        candidates.sort()
        best_distance, best_rank, best_candidate = candidates[0]
        if best_rank > 10_000:
            return word

        equally_close = [
            rank
            for distance, rank, _ in candidates
            if distance == best_distance and rank != best_rank
        ]
        if equally_close and best_rank * 2 >= min(equally_close):
            return word

        return self.preserve_case(word, best_candidate)

    def correct_message(self, message):
        return re.sub(
            r"[A-Za-z']+",
            lambda match: self.correct_word(match.group()),
            message,
        )

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

    def think(self, message, local_hour=None, conversation_history=None):

        message = self.normalize(self.correct_message(message))

        if not message:
            return "You haven't said anything yet."

        follow_up = self.respond_to_follow_up(
            message,
            conversation_history or [],
        )
        if follow_up is not None:
            return follow_up

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
                    return self.respond(intent, message, local_hour)

        # Look up a word entered directly.
        if message in self.vocabulary:
            self.last_topic = message
            return self.explain_word(message, "meaning")

        return None

    def respond_to_follow_up(self, message, conversation_history):
        affirmative_patterns = (
            r"yes",
            r"yeah",
            r"yep",
            r"yup",
            r"sure",
            r"okay",
            r"ok",
            r"of course",
            r"yes please",
            r"sure thing",
        )
        repeat_patterns = (
            r"what did you (?:just )?say",
            r"what was that",
            r"(?:can|could) you repeat(?: that)?(?: please)?",
            r"please repeat(?: that)?",
            r"say that again",
            r"repeat that",
            r"come again",
        )
        clarify_patterns = (
            r"what do you mean",
            r"what are you talking about",
            r"explain that",
            r"what does that mean",
        )
        is_repeat = any(
            re.fullmatch(pattern, message)
            for pattern in repeat_patterns
        )
        is_affirmative = any(
            re.fullmatch(pattern, message)
            for pattern in affirmative_patterns
        )
        is_clarification = any(
            re.fullmatch(pattern, message)
            for pattern in clarify_patterns
        )
        if not is_repeat and not is_clarification and not is_affirmative:
            return None

        latest_turn = next(
            (
                turn
                for turn in reversed(conversation_history)
                if turn.get("content", "").strip()
            ),
            None,
        )
        previous_reply = (
            latest_turn.get("content", "").strip()
            if latest_turn and latest_turn.get("role") == "assistant"
            else None
        )
        if is_affirmative:
            if previous_reply and previous_reply.endswith("?"):
                return self.response_engine.choose_response(
                    "affirmative_follow_up",
                    [
                        "Great! What would you like to dive into?",
                        "Sure—what would you like to talk about?",
                        "Absolutely. What do you have in mind?",
                        "Okay, I'm listening. Where shall we start?",
                        "Lovely. What would you like to explore?",
                    ],
                )
            return self.response_engine.choose_response(
                "standalone_affirmative",
                [
                    "Okay! What would you like to talk about?",
                    "Sure—what's on your mind?",
                    "All right. What can I help you with?",
                ],
            )

        if not previous_reply:
            return self.response_engine.choose_response(
                "missing_conversation_context",
                [
                    "I haven't replied in this chat yet. What would you like to ask me?",
                    "There's nothing for me to repeat just yet—send me a message and I'll respond.",
                    "I don't have an earlier reply in this chat. What can I help with?",
                ],
            )

        if is_repeat:
            return self.response_engine.choose_response(
                "repeat_previous_reply",
                [
                    f"I said: “{previous_reply}”",
                    f"My last reply was: “{previous_reply}”",
                    f"Just before that, I said: “{previous_reply}”",
                ],
            )

        return self.response_engine.choose_response(
            "clarify_previous_reply",
            [
                f"I was referring to my last reply: “{previous_reply}”",
                f"I meant what I said just before: “{previous_reply}”",
                f"My previous message was: “{previous_reply}”",
            ],
        )

    def respond(self, intent, message="", local_hour=None):
        return self.response_engine.respond_to_intent(
            intent,
            message,
            local_hour,
        )
