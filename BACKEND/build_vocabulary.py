
import json
import re
from pathlib import Path

from wordfreq import top_n_list
from nltk.corpus import wordnet as wn


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_DIR = Path(__file__).parent
VOCABULARY_FILE = BASE_DIR / "vocabulary.json"

TARGET = 50000
CANDIDATE_LIMIT = 60000


POS_NAMES = {
    "n": "noun",
    "v": "verb",
    "a": "adjective",
    "s": "adjective",
    "r": "adverb"
}


# --------------------------------------------------
# WORD INFORMATION
# --------------------------------------------------

def get_word_data(word):

    synsets = wn.synsets(word)

    if not synsets:
        return None

    main_sense = synsets[0]

    synonyms = set()
    antonyms = set()
    related_words = set()

    for sense in synsets[:5]:

        for lemma in sense.lemmas():

            name = lemma.name().replace("_", " ").lower()

            if name != word:
                synonyms.add(name)

            for opposite in lemma.antonyms():

                antonyms.add(
                    opposite.name().replace("_", " ").lower()
                )

            for related in lemma.derivationally_related_forms():

                related_words.add(
                    related.name().replace("_", " ").lower()
                )

    examples = main_sense.examples()

    return {
        "word": word,
        "meaning": main_sense.definition(),
        "type": POS_NAMES.get(main_sense.pos(), "other"),
        "example": examples[0] if examples else "",
        "synonyms": sorted(synonyms)[:10],
        "antonyms": sorted(antonyms)[:10],
        "related_words": sorted(related_words)[:10],
        "source": "WordNet"
    }


# --------------------------------------------------
# LOAD EXISTING VOCABULARY
# --------------------------------------------------

def load_vocabulary():

    if not VOCABULARY_FILE.exists():
        return []

    with open(VOCABULARY_FILE, "r", encoding="utf-8") as file:

        content = file.read().strip()

        if not content:
            return []

        data = json.loads(content)

        if not isinstance(data, list):
            raise ValueError(
                "vocabulary.json must contain a JSON list."
            )

        return data


# --------------------------------------------------
# SAVE VOCABULARY
# --------------------------------------------------

def save_vocabulary(vocabulary):

    temporary_file = VOCABULARY_FILE.with_suffix(".tmp")

    with open(temporary_file, "w", encoding="utf-8") as file:

        json.dump(
            vocabulary,
            file,
            indent=2,
            ensure_ascii=False
        )

    temporary_file.replace(VOCABULARY_FILE)


# --------------------------------------------------
# BUILD VOCABULARY
# --------------------------------------------------

def build_vocabulary():

    vocabulary = load_vocabulary()

    known_words = {
        item["word"].lower()
        for item in vocabulary
        if isinstance(item, dict) and "word" in item
    }

    print("=" * 50)
    print("VEN VOCABULARY BUILDER")
    print("=" * 50)

    print("Existing words:", len(vocabulary))
    print("Target words:", TARGET)

    # Enrich existing entries.
    print("\nEnriching existing vocabulary...")

    for index, item in enumerate(vocabulary):

        word = item["word"].lower()
        data = get_word_data(word)

        if data:

            for key, value in data.items():

                if key not in item or not item[key]:
                    item[key] = value

        if (index + 1) % 1000 == 0:
            print("Enriched:", index + 1)

    # Collect common English words.
    print("\nCollecting common English words...")

    candidates = top_n_list("en", CANDIDATE_LIMIT)

    added = 0
    checked = 0

    for word in candidates:

        if len(vocabulary) >= TARGET:
            break

        checked += 1

        word = word.lower().strip()

        if not re.fullmatch(r"[a-z]+", word):
            continue

        if word in known_words:
            continue

        data = get_word_data(word)

        if data is None:
            continue

        vocabulary.append(data)

        known_words.add(word)
        added += 1

        if added % 1000 == 0:

            print(
                f"New words: {added} | "
                f"Total words: {len(vocabulary)}"
            )

            # Save progress periodically.
            save_vocabulary(vocabulary)

    # Final save.
    save_vocabulary(vocabulary)

    print("\n" + "=" * 50)
    print("VOCABULARY BUILD COMPLETE")
    print("=" * 50)

    print("New words added:", added)
    print("Total words:", len(vocabulary))
    print("Candidates checked:", checked)

    if len(vocabulary) >= TARGET:

        print("VEN reached its 30,000-word target!")

    else:

        print(
            f"Target not reached. "
            f"Missing {TARGET - len(vocabulary)} words."
        )

        print(
            "Additional dictionary sources will be needed."
        )


# --------------------------------------------------
# START
# --------------------------------------------------

if __name__ == "__main__":

    try:
        build_vocabulary()

    except Exception as error:

        print("\nVocabulary building failed:")
        print(error)
        raise
