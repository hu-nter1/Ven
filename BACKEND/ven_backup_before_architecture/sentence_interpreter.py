
import spacy


class SentenceInterpreter:

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def interpret(self, sentence):

        doc = self.nlp(sentence.strip())

        if not doc:
            return {
                "sentence": sentence,
                "understood": False,
                "relationships": []
            }

        root = next(
            (token for token in doc if token.dep_ == "ROOT"),
            None
        )

        if root is None:
            return {
                "sentence": sentence,
                "understood": False,
                "relationships": []
            }

        relationships = []

        for token in doc:

            if token.is_punct or token.is_space:
                continue

            item = {
                "word": token.text,
                "lemma": token.lemma_,
                "type": token.pos_,
                "role": token.dep_,
                "connected_to": (
                    token.head.text
                    if token.head != token
                    else None
                )
            }

            relationships.append(item)

        main_verb = root

        if root.pos_ not in ("VERB", "AUX"):

            possible_verb = next(
                (
                    token for token in doc
                    if token.pos_ == "VERB"
                    and token.head == root
                ),
                None
            )

            if possible_verb:
                main_verb = possible_verb

        subjects = [
            token for token in doc
            if token.dep_ in ("nsubj", "nsubjpass", "csubj")
        ]

        objects = [
            token for token in doc
            if token.dep_ in ("dobj", "obj", "attr", "oprd")
        ]

        negation = any(
            token.dep_ == "neg"
            or token.lower_ in ("never", "n't")
            for token in doc
        )

        question_words = {
            "who", "what", "where", "when",
            "why", "how", "which", "whose", "whom"
        }

        question_word = next(
            (
                token.lower_
                for token in doc
                if token.lower_ in question_words
            ),
            None
        )

        auxiliary_inversion = any(
            token.pos_ == "AUX"
            and any(
                subject.i > token.i
                for subject in subjects
            )
            for token in doc
        )

        is_question = (
            sentence.strip().endswith("?")
            or question_word is not None
            or auxiliary_inversion
        )

        sentence_type = (
            "question" if is_question
            else "statement" if subjects
            else "possible_command"
        )

        return {
            "sentence": sentence,
            "understood": True,
            "sentence_type": sentence_type,
            "question_word": question_word,
            "main_action": (
                main_verb.lemma_
                if main_verb.pos_ in ("VERB", "AUX")
                else None
            ),
            "subjects": [
                self.get_phrase(token)
                for token in subjects
            ],
            "objects": [
                self.get_phrase(token)
                for token in objects
            ],
            "negation": negation,
            "relationships": relationships
        }

    def get_phrase(self, token):

        phrase_tokens = sorted(
            token.subtree,
            key=lambda item: item.i
        )

        return " ".join(
            item.text
            for item in phrase_tokens
            if not item.is_punct
        )


if __name__ == "__main__":

    interpreter = SentenceInterpreter()

    sentence = (
        "The intelligent young boy quickly "
        "eats a red apple in the kitchen."
    )

    result = interpreter.interpret(sentence)

    print("\nSENTENCE:", result["sentence"])
    print("ACTION:", result["main_action"])
    print("SUBJECTS:", result["subjects"])
    print("OBJECTS:", result["objects"])

    print("\nWORD RELATIONSHIPS:")

    for relationship in result["relationships"]:
        print(relationship)
