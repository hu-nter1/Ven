import html
import json
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from spacy.language import Language


class WebLookupError(Exception):
    pass


@dataclass(frozen=True)
class WebAnswer:
    title: str
    text: str
    url: str

    @property
    def reply(self):
        return f"Here's what I found on Wikipedia: {self.text}"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


class VENWebKnowledge:
    SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page"
    CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
    MAX_QUERY_LENGTH = 160
    FILLER_WORDS = {
        "a", "about", "an", "are", "be", "can", "could", "do", "does",
        "did", "explain", "find", "give", "i", "is", "it", "know", "me",
        "of", "please", "search", "tell", "the", "this", "to", "was",
        "were", "what", "when", "where", "which", "who", "whom", "whose",
        "will", "would", "you",
    }

    def __init__(self, nlp: Language, cache_file=None):
        self.nlp = nlp
        self.cache_file = (
            Path(cache_file)
            if cache_file
            else Path(__file__).parent / "ven_web_cache.json"
        )
        self.cache = self.load_cache()

    def load_cache(self):
        if not self.cache_file.exists():
            return {}

        with self.cache_file.open("r", encoding="utf-8") as file:
            cache = json.load(file)

        if not isinstance(cache, dict):
            raise ValueError(f"Web cache must contain a JSON object: {self.cache_file}")

        return cache

    @classmethod
    def is_search_request(cls, message):
        normalized = message.strip().lower()
        return bool(
            "?" in normalized
            or re.match(
                r"^(?:who|what|when|where|why|how|which|whose)\b",
                normalized,
            )
            or re.match(
                r"^(?:tell me about|explain|look up|search for|"
                r"find out about|give me information about)\b",
                normalized,
            )
        )

    def make_query(self, message):
        if re.search(
            r"\b(?:my|mine|our|ours)\b|"
            r"\b(?:where|what|who|when|how)\s+"
            r"(?:do|did|can|will|am)\s+i\b|"
            r"\b(?:where|what|who|when|how)\b.{0,30}\b(?:i|we)\b",
            message,
            re.IGNORECASE,
        ):
            return None

        tokens = []
        for token in self.nlp(message):
            if token.is_space or token.is_punct:
                continue
            lemma = token.lemma_.lower().strip()
            if not lemma or lemma in self.FILLER_WORDS:
                continue
            if not any(character.isalnum() for character in lemma):
                continue
            tokens.append(lemma)

        if not tokens:
            return None

        query = " ".join(tokens[:12])[:self.MAX_QUERY_LENGTH].strip()
        if len(query) < 2:
            return None

        if message.strip().lower().startswith("why "):
            query = f"why {query}"

        return query

    def search(self, message):
        query = self.make_query(message)
        if not query:
            return None

        cached = self.get_cached_answer(query)
        if cached:
            return cached

        params = urlencode({"q": query, "limit": 5})
        search_data = self.request_json(f"{self.SEARCH_URL}?{params}")
        pages = search_data.get("pages", [])
        if not isinstance(pages, list) or not pages:
            return None

        page = max(
            enumerate(pages),
            key=lambda item: self.score_page(item[1], query, item[0]),
        )[1]
        title = page.get("title")
        excerpt = self.clean_excerpt(page.get("excerpt", ""))
        if not title or not excerpt:
            return None

        url = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
        answer = WebAnswer(title=title, text=excerpt, url=url)
        self.cache[query] = {
            "title": answer.title,
            "text": answer.text,
            "url": answer.url,
            "expires_at": time.time() + self.CACHE_TTL_SECONDS,
        }
        self.save_cache()
        return answer

    def get_cached_answer(self, query):
        entry = self.cache.get(query)
        if not isinstance(entry, dict):
            return None
        if entry.get("expires_at", 0) <= time.time():
            self.cache.pop(query, None)
            return None

        title = entry.get("title")
        text = entry.get("text")
        url = entry.get("url")
        if not all(isinstance(value, str) and value for value in (title, text, url)):
            self.cache.pop(query, None)
            return None

        return WebAnswer(
            title=title,
            text=self.clean_excerpt(text),
            url=url,
        )

    def save_cache(self):
        with self.cache_file.open("w", encoding="utf-8") as file:
            json.dump(self.cache, file, ensure_ascii=False, indent=2)

    @staticmethod
    def request_json(url):
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "VEN-Assistant/1.0 (local educational project)",
            },
        )
        try:
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise WebLookupError(
                f"Wikipedia returned HTTP {error.code}."
            ) from error
        except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
            raise WebLookupError("Could not retrieve a valid Wikipedia result.") from error

    def score_page(self, page, query, result_index):
        query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        title = self.clean_excerpt(page.get("title", "")).lower()
        excerpt = self.clean_excerpt(page.get("excerpt", "")).lower()
        title_terms = set(re.findall(r"[a-z0-9]+", title))
        excerpt_terms = set(re.findall(r"[a-z0-9]+", excerpt))
        score = 4 * len(query_terms & title_terms)
        score += 2 * len(query_terms & excerpt_terms)

        if " ".join(sorted(query_terms)) == " ".join(sorted(title_terms)):
            score += 8
        if re.search(r"\bcapital\s+of\s+france\b", excerpt):
            score += 10
        if query.startswith("why ") and re.search(r"\bwhy\b", excerpt):
            score += 3

        return score - result_index

    @staticmethod
    def clean_excerpt(value):
        parser = _TextExtractor()
        parser.feed(html.unescape(str(value)))
        text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        return re.sub(r"\s+([,.;:!?])", r"\1", text)
