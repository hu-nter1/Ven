
import spacy


class SentenceInterpreter:

    def __init__(self):
        self.nlp = spacy.load("en_core_web_sm")

    def interpret(self, sentence):

        doc = self.nlp(sentence.strip())

        if not doc or not any(not token.is_space for token in doc):
            return {
                "sentence": sentence,
                "understood": False,
                "relationships": [],
                "clauses": []
            }

        relationships = []

        # Build a detailed representation of every word.
        for token in doc:

            if token.is_punct or token.is_space:
                continue

            children = [
                child.i
                for child in token.children
                if not child.is_punct
            ]

            relationships.append({
                "id": token.i,
                "word": token.text,
                "lemma": token.lemma_.lower(),
                "type": token.pos_,
                "tag": token.tag_,
                "role": token.dep_,
                "head_id": (
                    token.head.i
                    if token.head != token
                    else None
                ),
                "connected_to": (
                    token.head.text
                    if token.head != token
                    else None
                ),
                "children": children
            })

        # Identify the main grammatical clauses.
        clause_roots = [
            token
            for token in doc
            if token.dep_ == "ROOT"
            or token.dep_ in ("conj", "ccomp", "xcomp", "advcl", "relcl")
        ]

        clauses = []

        for root in clause_roots:

            subjects = [
                token
                for token in doc
                if token.dep_ in ("nsubj", "nsubjpass", "csubj")
                and (
                    token.head == root
                    or token.head.head == root
                )
            ]

            objects = [
                token
                for token in doc
                if token.dep_ in (
                    "dobj",
                    "obj",
                    "attr",
                    "acomp",
                    "oprd",
                    "dative"
                )
                and token.head == root
            ]

            auxiliaries = [
                token.lemma_.lower()
                for token in root.children
                if token.dep_ in ("aux", "auxpass")
            ]

            negation = any(
                token.dep_ == "neg"
                and (
                    token.head == root
                    or token.head.head == root
                )
                for token in doc
            )

            clauses.append({
                "root_id": root.i,
                "root_dependency": root.dep_,
                "parent_root_id": (
                    root.head.i
                    if root.head != root
                    else None
                ),
                "action": root.lemma_.lower(),
                "action_surface": root.text.lower(),
                "action_type": root.pos_,
                "subjects": [
                    self.get_phrase(token)
                    for token in subjects
                ],
                "objects": [
                    self.get_phrase(token)
                    for token in objects
                ],
                "object_types": [
                    token.pos_
                    for token in objects
                ],
                "auxiliaries": auxiliaries,
                "negation": negation
            })

        # Find question words.
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

        subjects = [
            token
            for token in doc
            if token.dep_ in ("nsubj", "nsubjpass", "csubj")
        ]

        objects = [
            token
            for token in doc
            if token.dep_ in ("dobj", "obj", "attr", "oprd", "dative")
        ]

        root = next(
            (token for token in doc if token.dep_ == "ROOT"),
            None
        )

        auxiliary_inversion = any(
            token.pos_ == "AUX"
            and any(subject.i > token.i for subject in subjects)
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

        # Identify descriptive properties.
        properties = []

        for token in doc:

            if token.dep_ in ("amod", "acomp", "attr", "advmod"):

                properties.append({
                    "word": token.lemma_.lower(),
                    "type": token.pos_,
                    "relationship": token.dep_,
                    "describes_id": token.head.i,
                    "describes": token.head.text
                })

        # Keep the original top-level fields for compatibility.
        main_action = None

        if root:

            if root.pos_ in ("VERB", "AUX"):
                main_action = root.lemma_.lower()

            else:
                possible_verb = next(
                    (
                        token
                        for token in doc
                        if token.pos_ == "VERB"
                        and token.head == root
                    ),
                    None
                )

                if possible_verb:
                    main_action = possible_verb.lemma_.lower()

        return {
            "sentence": sentence,
            "understood": True,
            "sentence_type": sentence_type,
            "question_word": question_word,
            "main_action": main_action,
            "subjects": [
                self.get_phrase(token)
                for token in subjects
            ],
            "objects": [
                self.get_phrase(token)
                for token in objects
            ],
            "negation": any(
                token.dep_ == "neg"
                or token.lower_ in ("never", "n't")
                for token in doc
            ),
            "properties": properties,
            "relationships": relationships,
            "clauses": clauses
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

    tests = [
        "The intelligent young boy quickly eats a red apple in the kitchen.",
        "Birds are animals.",
        "I can swim.",
        "John does not love Mary.",
        "The boy reads a book and writes a letter.",
        "Are you intelligent?"
    ]

    for sentence in tests:

        result = interpreter.interpret(sentence)

        print("\n" + "=" * 65)
        print("SENTENCE:", sentence)
        print("TYPE:", result["sentence_type"])
        print("ACTION:", result["main_action"])
        print("SUBJECTS:", result["subjects"])
        print("OBJECTS:", result["objects"])
        print("NEGATION:", result["negation"])

        print("\nPROPERTIES:")

        for item in result["properties"]:
            print(item)

        print("\nCLAUSES:")

        for clause in result["clauses"]:
            print(clause)

        print("\nWORD RELATIONSHIPS:")

        for relationship in result["relationships"]:
            print(relationship)
