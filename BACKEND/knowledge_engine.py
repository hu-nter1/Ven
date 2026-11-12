import json
import re
from collections import defaultdict, deque
from pathlib import Path

import spacy
from spacy.language import Language


class VENKnowledge:

    def __init__(self, facts=None, nlp: Language | None = None):
        self.nlp = nlp or spacy.load("en_core_web_sm")
        self.facts = facts if facts is not None else self.load_memory()
        self.common_facts = self.load_common_facts()

    @staticmethod
    def load_common_facts():
        common_facts_file = Path(__file__).parent / "common_facts.json"
        with common_facts_file.open("r", encoding="utf-8") as file:
            facts = json.load(file)

        if not isinstance(facts, list) or not all(
            isinstance(fact, dict) for fact in facts
        ):
            raise ValueError(
                f"Common facts must contain a JSON list: {common_facts_file}"
            )

        return facts

    @property
    def all_facts(self):
        return self.common_facts + self.facts

    @staticmethod
    def load_memory():
        from context_engine import VENContext

        return VENContext().facts

    @staticmethod
    def get_relation(fact):
        relation = fact.get("relation", fact.get("action"))
        if relation == "be":
            return "is_a"
        return relation

    def normalize(self, phrase):
        doc = self.nlp(phrase.lower())
        words = [
            token.lemma_.lower()
            for token in doc
            if not token.is_punct
            and token.pos_ not in ("DET",)
            and token.lower_ not in ("a", "an", "the")
        ]
        return " ".join(words)

    @staticmethod
    def get_modality(root):
        modalities = {
            "can": "ability",
            "will": "future",
            "must": "necessity",
            "may": "possibility",
            "might": "possibility",
            "should": "recommendation",
            "would": "conditional",
        }

        return next(
            (
                modalities[token.lemma_.lower()]
                for token in root.children
                if token.dep_ in ("aux", "auxpass")
                and token.lemma_.lower() in modalities
            ),
            None,
        )

    @staticmethod
    def get_phrase(token):
        return " ".join(
            item.text
            for item in sorted(token.subtree, key=lambda item: item.i)
            if not item.is_punct
        )

    def facts_matching(self, subject, relation, object_word=None, modality=None):
        normalized_subject = self.normalize(subject)
        normalized_object = (
            self.normalize(object_word) if object_word is not None else None
        )

        matches = []
        for fact in self.all_facts:
            if self.normalize(fact.get("subject", "")) != normalized_subject:
                continue
            if self.get_relation(fact) != relation:
                continue
            if fact.get("modality") != modality:
                continue

            fact_object = fact.get("object")
            if normalized_object is not None:
                if fact_object is None or self.normalize(fact_object) != normalized_object:
                    continue
            elif fact_object is not None:
                continue

            matches.append(fact)

        return matches

    def is_a_path(self, subject, object_word):
        start = self.normalize(subject)
        target = self.normalize(object_word)
        graph = defaultdict(list)

        for fact in self.all_facts:
            if (
                self.get_relation(fact) == "is_a"
                and not fact.get("negation", False)
                and not fact.get("modality")
                and fact.get("object")
            ):
                graph[self.normalize(fact["subject"])].append(
                    (self.normalize(fact["object"]), fact)
                )

        queue = deque([(start, [])])
        visited = {start}

        while queue:
            current, path = queue.popleft()
            for next_node, fact in graph[current]:
                next_path = path + [fact]
                if next_node == target:
                    return next_path
                if next_node not in visited:
                    visited.add(next_node)
                    queue.append((next_node, next_path))

        return None

    def answer(self, question):
        doc = self.nlp(question.strip())
        root = next((token for token in doc if token.dep_ == "ROOT"), None)
        if root is None:
            return "I couldn't understand that question."

        wh_word = next(
            (
                token.lower_
                for token in doc
                if token.lower_ in ("what", "who", "which")
            ),
            None,
        )
        subjects = [
            token for token in doc
            if token.dep_ in ("nsubj", "nsubjpass", "csubj")
            and token.head == root
            and token.lower_ not in ("what", "who", "which")
        ]
        subject = self.get_phrase(subjects[0]) if subjects else None
        is_known_relation = any(
            self.get_relation(fact) == root.lemma_.lower()
            for fact in self.all_facts
        )
        if (
            subject is None
            and root.pos_ == "NOUN"
            and is_known_relation
        ):
            subject_tokens = [
                token for token in doc
                if token.i < root.i
                and token.pos_ not in ("AUX", "DET", "PUNCT")
                and token.lower_ not in (
                    "what", "who", "which", "do", "does", "did"
                )
            ]
            if subject_tokens:
                subject = self.get_phrase(subject_tokens[-1])

        if wh_word:
            response = self.answer_wh_question(
                doc, root, wh_word, subject
            )
            if response is not None:
                return response

        subject, relation, object_word = self.get_question_relation(
            doc, root, subject
        )
        if not relation or not subject:
            return "I don't know that yet. You can teach me by telling me a fact."

        modality = self.get_modality(root)
        matches = self.facts_matching(
            subject, relation, object_word, modality
        )
        positive = [fact for fact in matches if not fact.get("negation", False)]
        negative = [fact for fact in matches if fact.get("negation", False)]

        if positive and negative:
            return "I have conflicting information about that."
        if positive:
            return self.format_yes_answer(
                subject, object_word, relation, positive
            )
        if negative:
            return self.format_no_answer(
                subject, object_word, relation, negative
            )

        if relation == "is_a" and object_word and modality is None:
            path = self.is_a_path(subject, object_word)
            if path:
                return self.format_inference(subject, object_word, path)

        return "I don't know that yet. You can teach me by telling me a fact."

    def answer_wh_question(self, doc, root, wh_word, subject):
        if root.lemma_.lower() == "be" and subject:
            categories = [
                fact.get("object")
                for fact in self.all_facts
                if self.normalize(fact.get("subject", "")) == self.normalize(subject)
                and self.get_relation(fact) == "is_a"
                and not fact.get("negation", False)
                and fact.get("object")
            ]
            if categories:
                source = next(
                    (
                        fact.get("source") or fact.get("original_sentence")
                        for fact in self.all_facts
                        if self.normalize(fact.get("subject", "")) == self.normalize(subject)
                        and self.get_relation(fact) == "is_a"
                        and not fact.get("negation", False)
                        and (fact.get("source") or fact.get("original_sentence"))
                    ),
                    None,
                )
                if source:
                    return f"I know this: {source.rstrip('.')}."
                return (
                    f"I know that {self.display(subject)} is a "
                    f"{self.display(categories[0])}."
                )

        is_known_relation = any(
            self.get_relation(fact) == root.lemma_.lower()
            for fact in self.all_facts
        )
        if root.pos_ in ("VERB", "AUX") or is_known_relation:
            object_wh = any(
                token.lower_ == wh_word
                and token.dep_ in ("dobj", "obj", "attr", "oprd")
                for token in doc
            )
            subject_wh = any(
                token.lower_ == wh_word
                and token.dep_ in ("nsubj", "nsubjpass")
                for token in doc
            )

            if subject and object_wh:
                values = [
                    fact.get("object")
                    for fact in self.all_facts
                    if self.normalize(fact.get("subject", "")) == self.normalize(subject)
                    and self.get_relation(fact) == root.lemma_.lower()
                    and not fact.get("negation", False)
                    and fact.get("object")
                ]
                if values:
                    fact = next(
                        (
                            item for item in self.all_facts
                            if self.normalize(item.get("subject", "")) == self.normalize(subject)
                            and self.get_relation(item) == root.lemma_.lower()
                            and self.normalize(item.get("object", "")) == self.normalize(values[0])
                            and not item.get("negation", False)
                        ),
                        None,
                    )
                    source = (
                        fact.get("source") or fact.get("original_sentence")
                        if fact
                        else None
                    )
                    if source:
                        return f"I know this: {source.rstrip('.')}."
                    return f"{self.display(subject)} {root.lemma_} {self.display(values[0])}."

            if subject_wh:
                object_tokens = [
                    token for token in doc
                    if token.dep_ in ("dobj", "obj")
                    and token.lower_ != wh_word
                ]
                object_word = (
                    self.get_phrase(object_tokens[0]) if object_tokens else None
                )
                matches = [
                    fact.get("subject")
                    for fact in self.all_facts
                    if self.get_relation(fact) == root.lemma_.lower()
                    and object_word
                    and fact.get("object")
                    and self.normalize(fact["object"]) == self.normalize(object_word)
                    and not fact.get("negation", False)
                ]
                if matches:
                    return f"{self.display(matches[0])}."

        return None

    def get_question_relation(self, doc, root, subject):
        is_copular = (
            root.lemma_.lower() == "be"
            or any(
                token.lemma_.lower() == "be"
                for token in root.children
                if token.dep_ in ("aux", "auxpass")
            )
        )

        if is_copular:
            subject_was_inferred = not subject
            if not subject:
                attribute = next(
                    (
                        token for token in root.children
                        if token.dep_ in ("attr", "acomp", "oprd")
                        and token.lower_ not in ("what", "who", "which")
                    ),
                    None,
                )
                if attribute is None:
                    return subject, None, None
                subject_tokens = [
                    token for token in doc
                    if token.i < attribute.i
                    and token.pos_ not in ("AUX", "PUNCT")
                    and token.lower_ not in ("a", "an", "the")
                ]
                subject = " ".join(token.text for token in subject_tokens)

            attribute = next(
                (
                    token for token in root.children
                    if token.dep_ in ("attr", "acomp", "oprd", "dobj")
                    and token.lower_ not in ("what", "who", "which")
                ),
                None,
            )
            if attribute is None:
                return subject, None, None

            if root.lemma_.lower() == "be":
                relation = (
                    "has_property"
                    if attribute.pos_ == "ADJ"
                    else "is_a"
                )
                object_word = (
                    attribute.text
                    if subject_was_inferred
                    else self.get_phrase(attribute)
                )
                return subject, relation, object_word
            object_word = self.get_phrase(attribute)
            if root.lemma_.lower() == "live":
                object_word = f"{root.text.lower()} {object_word}"
            return subject, "is_a", object_word

        is_known_relation = any(
            self.get_relation(fact) == root.lemma_.lower()
            for fact in self.all_facts
        )
        if root.pos_ == "VERB" or is_known_relation:
            object_token = next(
                (
                    token for token in root.children
                    if token.dep_ in ("dobj", "obj", "attr", "oprd")
                    and token.lower_ not in ("what", "who", "which")
                ),
                None,
            )
            if object_token is None:
                return subject, root.lemma_.lower(), None

            return subject, root.lemma_.lower(), self.get_phrase(object_token)

        return subject, None, None

    @staticmethod
    def display(value):
        words = re.sub(r"\s+", " ", value).strip()
        return words[:1].upper() + words[1:]

    def format_yes_answer(self, subject, object_word, relation, matches):
        source = next(
            (
                fact.get("source") or fact.get("original_sentence")
                for fact in matches
                if not fact.get("negation", False)
                and (fact.get("source") or fact.get("original_sentence"))
            ),
            None,
        )
        if source:
            return f"Yes. I know this: {source.rstrip('.')}."
        if object_word is None:
            return f"Yes. I know that {self.display(subject)} {relation}."
        if relation == "has_property":
            return f"Yes. I know that {self.display(subject)} is {self.display(object_word)}."
        return f"Yes. {self.display(subject)} is a {self.display(object_word)}."

    def format_no_answer(self, subject, object_word, relation, matches):
        source = next(
            (
                fact.get("source") or fact.get("original_sentence")
                for fact in matches
                if fact.get("negation", False)
                and (fact.get("source") or fact.get("original_sentence"))
            ),
            None,
        )
        if source:
            return f"No. I know this: {source.rstrip('.')}."
        if object_word is None:
            return f"No. I learned that {self.display(subject)} does not {relation}."
        if relation == "has_property":
            return f"No. I learned that {self.display(subject)} is not {self.display(object_word)}."
        return f"No. I learned that {self.display(subject)} is not a {self.display(object_word)}."

    def format_inference(self, subject, object_word, path):
        evidence = [
            fact.get("source") or fact.get("original_sentence")
            for fact in path
        ]
        evidence = [sentence.rstrip(".") for sentence in evidence if sentence]
        if evidence:
            return (
                f"Yes. I infer this from what I learned: "
                f"{' and '.join(evidence)}."
            )
        return (
            f"Yes. I infer that {self.display(subject)} is a "
            f"{self.display(object_word)} from what I know."
        )
