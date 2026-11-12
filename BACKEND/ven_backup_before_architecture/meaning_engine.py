
import re
import spacy
from nltk.corpus import wordnet as wn


class VENMeaningEngine:

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

        self.pos_mapping = {
            "NOUN": wn.NOUN,
            "VERB": wn.VERB,
            "ADJ": wn.ADJ,
            "ADV": wn.ADV
        }

        self.grammar_meanings = {
            "can": "Expresses ability or possibility",
            "will": "Expresses intention or future action",
            "must": "Expresses necessity or obligation",
            "may": "Expresses possibility or permission",
            "might": "Expresses possibility",
            "should": "Expresses advice or expectation",
            "would": "Expresses a possible or conditional action",
            "do": "Can form questions, negatives or emphasis",
            "be": "Expresses a state, identity or existence"
        }

        self.stop_words = self.nlp.Defaults.stop_words

    def get_words(self, text):

        return {
            word.lower()
            for word in re.findall(r"[a-z]+", text.lower())
            if word.lower() not in self.stop_words
        }

    def get_synsets(self, token):

        pos = self.pos_mapping.get(token.pos_)

        if pos:
            return wn.synsets(token.lemma_, pos=pos)

        return []

    def get_signature(self, synset):

        text = synset.definition()

        text += " " + " ".join(synset.examples())

        text += " " + " ".join(
            lemma.name().replace("_", " ")
            for lemma in synset.lemmas()
        )

        # Include the meaning of the parent concept.
        for parent in synset.hypernyms():
            text += " " + parent.definition()

        return self.get_words(text)

    def similarity(self, first, second):

        if first.pos() != second.pos():
            return None

        try:
            return first.wup_similarity(second)
        except Exception:
            return None

    def compare_senses(self, target_synset, context_tokens):

        target_signature = self.get_signature(target_synset)

        evidence = []

        for context_token in context_tokens:

            context_synsets = self.get_synsets(context_token)

            if not context_synsets:
                continue

            best_similarity = 0.0
            best_related_meaning = None

            for context_synset in context_synsets:

                context_signature = self.get_signature(
                    context_synset
                )

                common_words = (
                    target_signature.intersection(context_signature)
                )

                union_words = (
                    target_signature.union(context_signature)
                )

                lexical_similarity = (
                    len(common_words) / len(union_words)
                    if union_words else 0.0
                )

                semantic_similarity = self.similarity(
                    target_synset,
                    context_synset
                )

                if semantic_similarity is None:
                    semantic_similarity = 0.0

                combined_similarity = (
                    lexical_similarity * 0.5
                    + semantic_similarity * 0.5
                )

                if combined_similarity > best_similarity:

                    best_similarity = combined_similarity

                    best_related_meaning = (
                        context_synset.definition()
                    )

            if best_similarity > 0:

                evidence.append({
                    "context_word": context_token.text,
                    "context_role": context_token.dep_,
                    "similarity": round(best_similarity, 4),
                    "related_meaning": best_related_meaning
                })

        return evidence

    def interpret(self, sentence):

        doc = self.nlp(sentence.strip())

        results = []

        for token in doc:

            if token.is_punct or token.is_space:
                continue

            word_info = {
                "word": token.text,
                "lemma": token.lemma_,
                "part_of_speech": token.pos_,
                "grammatical_role": token.dep_,
                "meanings": [],
                "selected_meaning": None,
                "confidence": 0.0
            }

            # Handle grammatical auxiliary words.
            if token.pos_ == "AUX":

                if token.lemma_ in self.grammar_meanings:

                    word_info["meanings"].append(
                        self.grammar_meanings[token.lemma_]
                    )

                if token.lemma_ == "be":

                    word_info["usage"] = (
                        "Helping verb"
                        if token.dep_ == "aux"
                        else "Linking verb"
                    )

                elif token.tag_ == "MD":

                    word_info["usage"] = "Modal auxiliary"

                elif token.lemma_ == "do":

                    word_info["usage"] = "Auxiliary verb"

                results.append(word_info)
                continue

            # Handle content words using WordNet.
            if token.pos_ in self.pos_mapping:

                synsets = self.get_synsets(token)

                context_tokens = [
                    other
                    for other in doc
                    if other.i != token.i
                    and not other.is_punct
                    and not other.is_stop
                    and other.pos_ in self.pos_mapping
                ]

                candidates = []

                for synset in synsets:

                    evidence = self.compare_senses(
                        synset,
                        context_tokens
                    )

                    score = (
                        sum(item["similarity"] for item in evidence)
                        / len(evidence)
                        if evidence else 0.0
                    )

                    candidates.append({
                        "definition": synset.definition(),
                        "part_of_speech": synset.pos(),
                        "score": round(score, 4),
                        "evidence": evidence
                    })

                candidates.sort(
                    key=lambda item: item["score"],
                    reverse=True
                )

                word_info["meanings"] = candidates

                if candidates:

                    best = candidates[0]

                    second_score = (
                        candidates[1]["score"]
                        if len(candidates) > 1
                        else 0.0
                    )

                    difference = best["score"] - second_score

                    # Require some evidence and a meaningful
                    # difference before choosing a sense.
                    if best["score"] >= 0.03 and (
                        len(candidates) == 1
                        or difference >= 0.01
                    ):

                        word_info["selected_meaning"] = (
                            best["definition"]
                        )

                        word_info["confidence"] = best["score"]

            results.append(word_info)

        return results


if __name__ == "__main__":

    ven = VENMeaningEngine()

    sentences = [
        "The child swam across the river.",
        "I opened a can.",
        "What do you know?",
        "I do my work.",
        "Are you intelligent?",
        "Birds are animals."
    ]

    for sentence in sentences:

        print("\nSENTENCE:", sentence)
        print("=" * 65)

        for word in ven.interpret(sentence):

            print("\nWORD:", word["word"])
            print("TYPE:", word["part_of_speech"])
            print("ROLE:", word["grammatical_role"])

            if "usage" in word:
                print("USAGE:", word["usage"])

            if word["selected_meaning"]:

                print(
                    "SELECTED MEANING:",
                    word["selected_meaning"]
                )

                print(
                    "CONFIDENCE:",
                    word["confidence"]
                )

            elif word["meanings"]:

                print("SELECTED MEANING: Uncertain")

            else:

                print("MEANINGS:", word["meanings"])

            if word["meanings"]:

                print("POSSIBLE MEANINGS:")

                for meaning in word["meanings"][:3]:

                    print(
                        " ",
                        meaning["definition"],
                        "| score:",
                        meaning["score"]
                    )
