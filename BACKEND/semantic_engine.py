
from sentence_interpreter import SentenceInterpreter


class VENSemanticEngine:

    def __init__(self, interpreter=None):
        self.interpreter = interpreter or SentenceInterpreter()

    def interpret(self, sentence):

        parsed = self.interpreter.interpret(sentence)

        if not parsed.get("understood"):
            return {
                "understood": False,
                "sentence": sentence,
                "sentence_type": parsed.get("sentence_type"),
                "propositions": []
            }

        sentence_type = parsed.get("sentence_type")

        if sentence_type != "statement":
            return {
                "understood": True,
                "sentence": sentence,
                "sentence_type": sentence_type,
                "propositions": []
            }

        propositions = []
        clauses = parsed.get("clauses", [])

        subjects_by_root = {}

        for clause in clauses:
            subjects = clause.get("subjects", [])
            objects = clause.get("objects", [])
            action = clause.get("action")
            auxiliaries = clause.get("auxiliaries", [])
            negation = clause.get("negation", False)

            if not subjects and clause.get("root_dependency") == "conj":
                parent_subjects = subjects_by_root.get(
                    clause.get("parent_root_id"),
                    []
                )
                subjects = parent_subjects

            subjects_by_root[clause.get("root_id")] = subjects

            for subject in subjects:
                if not action:
                    continue

                if action == "be":
                    object_types = clause.get("object_types", [])
                    for object_index, obj in enumerate(objects):
                        object_type = (
                            object_types[object_index]
                            if object_index < len(object_types)
                            else None
                        )
                        relation = (
                            "has_property"
                            if object_type == "ADJ"
                            else "is_a"
                        )
                        propositions.append(
                            self.make_proposition(
                                subject,
                                relation,
                                obj,
                                negation,
                                None,
                                sentence
                            )
                        )

                elif action == "live" and "be" in auxiliaries and objects:
                    propositions.append(
                        self.make_proposition(
                            subject,
                            "is_a",
                            (
                                f"{clause.get('action_surface', 'living')} "
                                f"{objects[0]}"
                            ),
                            negation,
                            None,
                            sentence
                        )
                    )

                else:
                    modality = self.get_modality(auxiliaries)
                    object_word = objects[0] if objects else None
                    propositions.append(
                        self.make_proposition(
                            subject,
                            action,
                            object_word,
                            negation,
                            modality,
                            sentence
                        )
                    )

        return {
            "understood": bool(propositions),
            "sentence": sentence,
            "sentence_type": sentence_type,
            "propositions": propositions
        }

    @staticmethod
    def get_modality(auxiliaries):
        modalities = {
            "can": "ability",
            "will": "future",
            "must": "necessity",
            "may": "possibility",
            "might": "possibility",
            "should": "recommendation",
            "would": "conditional"
        }

        return next(
            (modalities[item] for item in auxiliaries if item in modalities),
            None
        )

    @staticmethod
    def make_proposition(
        subject,
        relation,
        object_word,
        negation,
        modality,
        sentence
    ):
        return {
            "subject": subject.lower(),
            "relation": relation.lower(),
            "object": object_word.lower() if object_word else None,
            "negation": bool(negation),
            "modality": modality,
            "source": sentence,
            "origin": "explicit"
        }


if __name__ == "__main__":

    ven = VENSemanticEngine()

    tests = [
        "Birds are animals.",
        "Animals are living things.",
        "John loves Mary.",
        "John does not love Mary.",
        "John is intelligent.",
        "I can swim.",
        "The boy reads a book and writes a letter."
    ]

    for sentence in tests:

        result = ven.interpret(sentence)

        print("\nSENTENCE:", sentence)
        print("=" * 60)

        for proposition in result["propositions"]:
            print(proposition)

        if not result["propositions"]:
            print("VEN could not construct a proposition.")
