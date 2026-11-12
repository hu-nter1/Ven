import html
import ipaddress
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

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
        return f"Here's a result from the web: {self.text}"


class _SearchResultsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    @classmethod
    def parse(cls, document):
        root = ElementTree.fromstring(document)
        results = []
        for item in root.findall(".//item"):
            title = item.findtext("title", default="")
            excerpt = item.findtext("description", default="")
            url = cls.extract_result_url(item.findtext("link", default=""))
            title = cls.clean_text(title)
            excerpt = cls.clean_text(excerpt)
            if title and excerpt and url:
                results.append({
                    "title": title,
                    "excerpt": excerpt,
                    "url": url,
                })
        return results

    @staticmethod
    def extract_result_url(href):
        candidate = urljoin("https://www.bing.com", href)
        try:
            parsed = urlparse(candidate)
            host = parsed.hostname
        except ValueError:
            return ""
        if host in ("bing.com", "www.bing.com"):
            target = parse_qs(parsed.query).get("uddg", [None])[0]
            if not target:
                return ""
            candidate = target

        try:
            target = urlparse(candidate)
            hostname = target.hostname
            port = target.port
        except ValueError:
            return ""
        if (
            target.scheme not in ("http", "https")
            or not hostname
            or target.username
            or target.password
            or port not in (None, 80, 443)
        ):
            return ""
        normalized_host = hostname.lower()
        if (
            normalized_host == "duckduckgo.com"
            or normalized_host.endswith(".duckduckgo.com")
            or normalized_host == "localhost"
            or normalized_host.endswith(".local")
            or normalized_host == "bing.com"
            or normalized_host.endswith(".bing.com")
        ):
            return ""
        try:
            if not ipaddress.ip_address(normalized_host).is_global:
                return ""
        except ValueError:
            pass
        return candidate

    @staticmethod
    def clean_text(value):
        parser = _SearchResultsParser()
        parser.feed(html.unescape(str(value)))
        text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        return re.sub(r"\s+([,.;:!?])", r"\1", text)


class VENWebKnowledge:
    SEARCH_URL = "https://www.bing.com/search"
    INSTANT_ANSWER_URL = "https://api.duckduckgo.com/"
    WIKIPEDIA_SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page"
    CACHE_TTL_SECONDS = 7 * 24 * 60 * 60
    MAX_QUERY_LENGTH = 160
    MAX_EXCERPT_LENGTH = 1000
    FILLER_WORDS = {
        "a", "about", "an", "are", "be", "can", "could", "do", "does",
        "did", "explain", "find", "give", "i", "is", "it", "know", "me",
        "please", "search", "tell", "the", "this", "to", "was",
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
            r"\b(?:where|what|who|when|how)\b.{0,30}\b(?:i|me|we|us)\b",
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

        cache_key = f"public-web:{query}"
        cached = self.get_cached_answer(cache_key)
        if cached:
            return cached

        answer = None
        last_error = None
        params = urlencode({"q": query, "format": "rss"})
        try:
            pages = self.request_results(f"{self.SEARCH_URL}?{params}")
            pages = [
                page for page in pages
                if self.page_matches_query(page, query)
            ]
            if pages:
                page = max(
                    enumerate(pages),
                    key=lambda item: self.score_page(item[1], query, item[0]),
                )[1]
                answer = WebAnswer(
                    title=page["title"],
                    text=page["excerpt"],
                    url=page["url"],
                )
        except WebLookupError as error:
            last_error = error

        if answer is None:
            try:
                answer = self.search_instant_answers(query)
            except WebLookupError as error:
                last_error = error

        if answer is None:
            try:
                answer = self.search_wikipedia(query)
            except WebLookupError as error:
                last_error = error

        if answer is None and last_error is not None:
            raise WebLookupError(
                "Public search providers could not return a result."
            ) from last_error
        if answer is None:
            return None

        self.cache[cache_key] = {
            "title": answer.title,
            "text": answer.text,
            "url": answer.url,
            "expires_at": time.time() + self.CACHE_TTL_SECONDS,
        }
        self.save_cache()
        return answer

    def search_instant_answers(self, query):
        params = urlencode({
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        })
        data = self.request_json(f"{self.INSTANT_ANSWER_URL}?{params}")
        title = data.get("Heading") or data.get("AbstractSource")
        text = data.get("AbstractText") or data.get("Answer")
        url = data.get("AbstractURL")
        if (
            title
            and text
            and url
            and self.page_matches_query(
                {"title": title, "excerpt": text},
                query,
            )
        ):
            safe_url = _SearchResultsParser.extract_result_url(url)
            if safe_url:
                return WebAnswer(
                    title=_SearchResultsParser.clean_text(title),
                    text=self.limit_excerpt(
                        _SearchResultsParser.clean_text(text)
                    ),
                    url=safe_url,
                )

        for result in data.get("Results", []):
            answer = self.instant_result(result, query)
            if answer:
                return answer

        return None

    def instant_result(self, result, query):
        if not isinstance(result, dict):
            return None
        title = result.get("FirstURL")
        text = result.get("Text")
        if title and text and self.page_matches_query(
            {"title": title, "excerpt": text},
            query,
        ):
            safe_url = _SearchResultsParser.extract_result_url(title)
            if safe_url:
                label = _SearchResultsParser.clean_text(text)
                return WebAnswer(
                    title=label.split(" - ", 1)[0],
                    text=label,
                    url=safe_url,
                )

        for child in result.get("Topics", []):
            answer = self.instant_result(child, query)
            if answer:
                return answer
        return None

    def search_wikipedia(self, query):
        params = urlencode({"q": query, "limit": 5})
        data = self.request_json(f"{self.WIKIPEDIA_SEARCH_URL}?{params}")
        pages = data.get("pages", [])
        if not isinstance(pages, list) or not pages:
            return None
        pages = [
            page for page in pages
            if self.page_matches_query({
                "title": page.get("title", ""),
                "excerpt": page.get("excerpt", ""),
            }, query)
        ]
        if not pages:
            return None

        page = max(
            enumerate(pages),
            key=lambda item: self.score_page({
                "title": item[1].get("title", ""),
                "excerpt": item[1].get("excerpt", ""),
            }, query, item[0]),
        )[1]
        title = page.get("title")
        text = _SearchResultsParser.clean_text(page.get("excerpt", ""))
        if not title or not text:
            return None

        page_key = page.get("key") or title.replace(" ", "_")
        return WebAnswer(
            title=title,
            text=self.limit_excerpt(text),
            url=f"https://en.wikipedia.org/wiki/{quote(page_key, safe='')}",
        )

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
        safe_url = _SearchResultsParser.extract_result_url(url)
        if not safe_url:
            self.cache.pop(query, None)
            return None

        return WebAnswer(
            title=title,
            text=_SearchResultsParser.clean_text(text),
            url=safe_url,
        )

    @classmethod
    def limit_excerpt(cls, text):
        if len(text) <= cls.MAX_EXCERPT_LENGTH:
            return text
        excerpt = text[:cls.MAX_EXCERPT_LENGTH]
        boundary = excerpt.rfind(" ")
        return f"{excerpt[:boundary if boundary > 0 else len(excerpt)]}…"

    def save_cache(self):
        with self.cache_file.open("w", encoding="utf-8") as file:
            json.dump(self.cache, file, ensure_ascii=False, indent=2)

    @classmethod
    def request_results(cls, url):
        request = Request(
            url,
            headers={
                "Accept": "application/rss+xml, application/xml, text/xml",
                "User-Agent": "Mozilla/5.0 (compatible; VEN/1.0; local assistant)",
            },
        )
        try:
            with urlopen(request, timeout=5) as response:
                document = response.read(2_000_000).decode("utf-8")
        except HTTPError as error:
            raise WebLookupError(
                f"The public search provider returned HTTP {error.code}."
            ) from error
        except (URLError, TimeoutError, UnicodeDecodeError) as error:
            raise WebLookupError(
                "Could not retrieve valid public search results."
            ) from error

        try:
            return _SearchResultsParser.parse(document)
        except ElementTree.ParseError as error:
            raise WebLookupError(
                "The public search provider returned invalid results."
            ) from error

    @staticmethod
    def request_json(url):
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "VEN/1.0 (local assistant)",
            },
        )
        try:
            with urlopen(request, timeout=5) as response:
                data = json.loads(response.read(2_000_000).decode("utf-8"))
        except HTTPError as error:
            raise WebLookupError(
                f"A public search provider returned HTTP {error.code}."
            ) from error
        except (
            URLError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise WebLookupError(
                "Could not retrieve valid public search data."
            ) from error
        if not isinstance(data, dict):
            raise WebLookupError("A public search provider returned invalid data.")
        return data

    def score_page(self, page, query, result_index):
        query_words = self.normalize_terms(query)
        query_terms = set(query_words)
        title_words = self.normalize_terms(page.get("title", ""))
        excerpt = page.get("excerpt", "").lower()
        excerpt_words = self.normalize_terms(excerpt)
        title_terms = set(title_words)
        excerpt_terms = set(excerpt_words)
        score = 4 * len(query_terms & title_terms)
        score += 2 * len(query_terms & excerpt_terms)
        if title_terms and query_terms <= title_terms:
            score += 8
        score += self.proximity_score(query_terms, title_words) * 2
        score += self.proximity_score(query_terms, excerpt_words)
        if query.startswith("why ") and re.search(r"\bwhy\b", excerpt):
            score += 3

        return score - result_index

    @classmethod
    def page_matches_query(cls, page, query):
        query_terms = set(cls.normalize_terms(query))
        page_terms = set(cls.normalize_terms(
            f"{page.get('title', '')} {page.get('excerpt', '')}"
        ))
        if not query_terms & page_terms:
            return False

        capital_query = re.search(
            r"\bcapitals?\s+of\s+(.+)$",
            query.lower(),
        )
        if capital_query:
            country = re.escape(capital_query.group(1).strip())
            capital_reference = re.compile(
                rf"\bcapitals?(?:\s+city)?\s+of\s+{country}\b"
            )
            page_text = (
                f"{page.get('title', '')} {page.get('excerpt', '')}"
            ).lower()
            return bool(capital_reference.search(page_text))

        return True

    @staticmethod
    def normalize_terms(text):
        words = re.findall(r"[a-z0-9]+", text.lower())
        return [
            word[:-1] if len(word) > 3 and word.endswith("s") else word
            for word in words
        ]

    @staticmethod
    def proximity_score(query_terms, page_words):
        if not query_terms:
            return 0

        required = Counter(query_terms)
        window = Counter()
        left = 0
        matched = 0
        shortest = None

        for right, word in enumerate(page_words):
            window[word] += 1
            if window[word] <= required[word]:
                matched += 1
            while matched == len(query_terms):
                span = right - left + 1
                shortest = span if shortest is None else min(shortest, span)
                left_word = page_words[left]
                window[left_word] -= 1
                if window[left_word] < required[left_word]:
                    matched -= 1
                left += 1

        if shortest is None:
            return 0
        return max(0, 8 - 2 * (shortest - len(query_terms)))
