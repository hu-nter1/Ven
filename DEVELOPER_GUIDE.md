# VEN Developer Guide

This guide covers the current app and API implementation. For a quick project introduction and first-run instructions, see the [README](README.md).

## Architecture

```text
Microphone
   │
   ▼
Expo app (FRONTEND)
   ├── speech recognition → transcript
   ├── POST /chat ───────────────► FastAPI (BACKEND)
   │                                  ├── VENBrain + vocabulary.json
   │                                  ├── VENResponseEngine
   │                                  ├── common_facts.json + local learning
   │                                  └── public web search → local cache
   └── response text ◄──── reply + optional source citation
          └── expo-speech reads reply aloud
```

The frontend owns speech capture, conversation display, and text-to-speech. It saves up to 50 recent conversations on-device with AsyncStorage and sends up to eight recent turns with each request so `VENBrain` can handle repeat, clarification, and affirmative follow-ups; the backend does not persist chat history. Before routing a turn, `VENBrain` corrects a small set of common speech-recognition contractions and high-confidence misspellings using the vocabulary, while protecting common English function words and leaving ambiguous or uncommon candidates unchanged. `VENBrain` also handles vocabulary questions and conversational intents; `VENResponseEngine` composes varied rule-based replies from interpreted statements and combines greeting variations across time periods. Local facts come from `common_facts.json` and explicit learned statements in `ven_memory.json`; questions are not saved as facts. The drawer's Memory view reads and deletes these learned facts through the memory API. If local knowledge cannot answer an information request, the backend tries Bing's public RSS search, a DuckDuckGo instant answer, and then Wikipedia, returning the selected excerpt and citation. Search terms preserve important word forms, and results need to match multiple query terms when the query contains more than one. Results are cached in `ven_web_cache.json`. No hosted generative-AI model or search API key is used.

## Requirements

- Node.js and npm for the Expo app.
- Python 3 for the API.
- A device or simulator that can reach the API over the network.

## Frontend

### Install and run

```bash
cd FRONTEND
npm ci
npx expo start
```

Run the app on Android, iOS, or web using the Expo CLI. Speech recognition and VEN's Android background-listening service require a development build, not Expo Go. After changing native configuration or the local native module, regenerate/build the Android app:

```bash
npx expo run:android
npx expo start --dev-client
```

The project uses Continuous Native Generation, so configure native behavior through `app.json`, config plugins, and local Expo modules rather than hand-editing generated `ios/` or `android/` directories.

On Android, tapping **Start listening** starts a microphone foreground service and displays an ongoing notification. Android 13 and later require notification permission for the visible notification. The home screen passes listening state to the video background, which resumes playback if the native player pauses while speech recognition is active. Tapping **Stop listening** stops recognition and removes the notification. Android may still stop microphone work if the user force-stops the app, revokes permissions, or device-specific battery controls terminate it. iOS does not use this Android service and remains subject to iOS background speech-recognition restrictions.

The Android foreground service keeps the user-requested listening task active; the operating system's speech-recognition provider still performs transcription and may impose its own limits or require network access. The service does not provide wake-word detection and cannot restart VEN after the user force-stops the app.

The backend base URL is currently a source constant named `API_URL` in `src/components/ven-speech.tsx`. Update it for the target running the app:

| Target | Typical local API URL |
| --- | --- |
| iOS simulator | `http://127.0.0.1:8000` |
| Android emulator | `http://10.0.2.2:8000` |
| Physical device | `http://<computer-LAN-IP>:8000` |

For a physical device, bind the backend to `0.0.0.0`, keep both devices on the same network, and use the computer’s LAN address. The current backend is plain HTTP and has no authentication; use it for local development only.

### Project layout

- `src/app/` — Expo Router routes. `index.tsx` composes the home screen, while `explore.tsx` is still starter/template content.
- `src/components/ven-speech.tsx` — microphone control, speech-recognition event handling, chat UI, API request, and spoken reply.
- Recent chats are persisted in the browser/app's local AsyncStorage store under `ven.recent-chats.v1`; they are not synchronized to the backend. The drawer can switch among saved chats, start a fresh chat, and delete the active chat.
- The drawer's Memory view uses the backend memory endpoints to review facts in `ven_memory.json` and forget selected facts. Memory access requires the API to be running.
- `src/components/ven-sky-background.tsx` and `ven-avatar.tsx` — home-screen media.
- `src/components/app-tabs.tsx` and `app-tabs.web.tsx` — platform-specific tab navigation.
- `app.json` — app identity, platform permissions, and native plugins.
- `assets/` — app artwork, icons, and video.

Keep route screens in `src/app/`; put reusable UI and logic elsewhere in `src/`.

### Frontend checks

From `FRONTEND/`:

```bash
npx expo lint
npx tsc --noEmit
```

There is no test script currently configured in `package.json`.

### Android development and standalone APKs

The Android debug build is a development-client app named **Ven Dev**. It has a `.dev` application ID suffix, so it can be installed alongside the standalone app. Start Metro with:

```bash
cd FRONTEND
npx expo start --dev-client
```

In another terminal, build and install the development APK:

```bash
cd FRONTEND/android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

The standalone release embeds the JavaScript bundle and runs without Metro:

```bash
cd FRONTEND/android
./gradlew assembleRelease
adb install -r app/build/outputs/apk/release/app-release.apk
```

The local release build is signed with the checked-in debug signing configuration for sideloading. Create and configure a private release keystore before distributing the APK outside local development; never publish the debug key as a production signing key.

## Backend

### Install and run

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install fastapi "uvicorn[standard]" spacy
python -m spacy download en_core_web_sm
cd BACKEND
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API is defined in `main.py`:

- `GET /` — health/status response.
- `POST /chat` — accepts `{"message": "..."}`, an optional device-local `local_hour` from 0 to 23, an optional `new_conversation` flag, and up to eight optional `conversation_history` turns (`role` is `user` or `assistant`, with a `content` string). The mobile app sends its local hour for time-aware greetings and recent turns for contextual follow-ups. Starting a new conversation resets the vocabulary follow-up topic; history is request context only and is not persisted. It returns `{"reply": "..."}`, optionally with `source_title` and `source_url` for web-backed answers.
- `GET /memory` — returns learned facts as `{"facts": [...]}`.
- `DELETE /memory/{fact_index}` — forgets the fact at that zero-based index and returns the remaining facts. It returns 404 if the index is not present.

For example:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is the capital of France?","local_hour":13,"conversation_history":[]}'
```

FastAPI’s interactive documentation is available at `http://127.0.0.1:8000/docs`.

The sentence interpreter uses the `en_core_web_sm` spaCy model. Its semantic propositions are the representation written for new facts; existing `ven_memory.json` records in the earlier `subject`/`action` format are preserved and remain readable by the basic question-answering code. WordNet-based word meaning and the experimental reasoning module are not yet part of the `/chat` pipeline.

Run the backend regression tests from the repository root with:

```bash
python -m unittest discover -s BACKEND -p 'test_*.py'
```

### Conversation logic

`brain.py` defines `VENBrain`. It loads `vocabulary.json`, handles word requests, and remembers the last looked-up word so follow-ups such as “give an example” can use it. If an entry has no example, it composes a sentence from the word type and definition instead of returning a generic learning fallback.

`response_engine.py` builds conversational responses from parsed propositions and rotates among alternative phrasings so consecutive greetings and personal-statement replies do not repeat exactly. This is rule-based response composition, not a local or hosted language model; improve it with reusable language mechanisms rather than a response for each exact sentence.

### Vocabulary data and builder

`vocabulary.json` is a JSON list. An entry can include:

```json
{
  "word": "curious",
  "meaning": "Eager to know or learn something.",
  "type": "adjective",
  "example": "",
  "synonyms": [],
  "antonyms": [],
  "related_words": [],
  "source": "WordNet"
}
```

The runtime needs only the JSON file and the FastAPI dependencies. The optional `build_vocabulary.py` tool imports `wordfreq` and NLTK WordNet. To run it:

```bash
cd BACKEND
python -m pip install wordfreq nltk
python -m nltk.downloader wordnet omw-1.4
python build_vocabulary.py
```

The builder enriches existing entries and attempts to grow the list to its configured 50,000-word target. It writes the resulting data to `vocabulary.json`; review the diff before keeping generated changes. The vocabulary source attribution is recorded per entry.

## API contract and current limitations

The `/chat` endpoint takes a string `message` and returns a string `reply`, with optional `source_title` and `source_url` fields when web search is used. Request validation is handled by Pydantic. The backend currently has no database, authentication, rate limiting, or CORS middleware. In particular, browser-based frontend requests from a different origin need a CORS policy before the web app can use the API. Speech recognition availability and permissions vary by platform and device.

### Local learning and reasoning

VEN does not call a hosted generative-AI API and does not train a language model. Built-in facts in `common_facts.json` are available without network access and are not copied into user memory. Declarative statements the local sentence interpreter can represent are saved in `ven_memory.json`; direct and transitive `is_a` relationships can then answer simple questions such as “Are birds living things?” from “Birds are animals” and “Animals are living things.” This is a small, explainable knowledge-inference step, not general human-like understanding.

When local knowledge cannot answer an information request, `web_knowledge.py` sends cleaned search terms to Bing's public RSS search, then tries a DuckDuckGo instant answer and Wikipedia as fallbacks. It returns an indexed result excerpt with a clickable citation and caches results locally in `ven_web_cache.json` for seven days. This is search-result retrieval, not a crawler: it cannot guarantee coverage of every website or read private, paywalled, blocked, or unindexed pages. Search providers may rate-limit or change their pages. Web lookup needs internet access and sends the cleaned search query to those providers. The cache and learned facts are local development data and should not be committed. Rule-based phrasing does not provide open-ended language-model generation, and web retrieval does not make the device's speech-recognition provider offline.

## Troubleshooting

- **The app says it cannot connect:** confirm the API is running, then check `API_URL`. A phone cannot use the developer computer’s `127.0.0.1`; use its LAN IP instead.
- **The API starts but vocabulary lookup fails:** confirm `BACKEND/vocabulary.json` exists and contains a JSON list.
- **The microphone does not start:** grant microphone and speech-recognition permissions, confirm the platform has a recognition service, and try a development build if the native module is missing.
- **The web app cannot call the API:** configure CORS on the backend for the frontend’s development origin.
- **Vocabulary generation reports missing NLTK data:** download `wordnet` and `omw-1.4` into the same Python environment used to run the builder.
