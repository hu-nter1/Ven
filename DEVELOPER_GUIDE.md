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
   │                                  ├── common_facts.json + local learning
   │                                  └── Wikipedia fallback → local cache
   └── response text ◄──── reply + optional source citation
          └── expo-speech reads reply aloud
```

The frontend owns speech capture, conversation display, and text-to-speech. The backend first processes input with the vocabulary responder and local knowledge. It loads built-in offline facts from `common_facts.json` and stores explicit learned statements in `ven_memory.json`; questions are not saved as facts. If local knowledge cannot answer an information request, the backend searches Wikipedia and returns an excerpt with a source citation. The result cache is stored in `ven_web_cache.json`. The backend does not call a generative-AI service or store chat history.

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

On Android, tapping **Start listening** starts a microphone foreground service and displays an ongoing notification. Android 13 and later require notification permission for the visible notification. Tapping **Stop listening** stops recognition and removes the notification. Android may still stop microphone work if the user force-stops the app, revokes permissions, or device-specific battery controls terminate it. iOS does not use this Android service and remains subject to iOS background speech-recognition restrictions.

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
- `POST /chat` — accepts `{"message": "..."}` and returns `{"reply": "..."}`, optionally with `source_title` and `source_url` for Wikipedia-backed answers.

For example:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is the capital of France?"}'
```

FastAPI’s interactive documentation is available at `http://127.0.0.1:8000/docs`.

The sentence interpreter uses the `en_core_web_sm` spaCy model. Its semantic propositions are the representation written for new facts; existing `ven_memory.json` records in the earlier `subject`/`action` format are preserved and remain readable by the basic question-answering code. WordNet-based word meaning and the experimental reasoning module are not yet part of the `/chat` pipeline.

Run the backend regression tests from the repository root with:

```bash
python -m unittest discover -s BACKEND -p 'test_*.py'
```

### Conversation logic

`brain.py` defines `VENBrain`. On startup it loads `vocabulary.json` relative to the module, indexes entries by lowercase `word`, normalizes incoming messages, checks configured conversational intents, and then handles vocabulary question patterns or direct word lookups. Unsupported messages receive a learning/fallback response.

To add a conversational intent, update the intent phrases and corresponding response in `VENBrain`. Keep behavior and normalization in sync when adding new kinds of vocabulary questions.

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

The `/chat` endpoint takes a string `message` and returns a string `reply`, with optional `source_title` and `source_url` fields when Wikipedia is used. Request validation is handled by Pydantic. The backend currently has no database, authentication, rate limiting, or CORS middleware. In particular, browser-based frontend requests from a different origin need a CORS policy before the web app can use the API. Speech recognition availability and permissions vary by platform and device.

### Local learning and reasoning

VEN does not call a hosted generative-AI API and does not train a language model. Built-in facts in `common_facts.json` are available without network access and are not copied into user memory. Declarative statements the local sentence interpreter can represent are saved in `ven_memory.json`; direct and transitive `is_a` relationships can then answer simple questions such as “Are birds living things?” from “Birds are animals” and “Animals are living things.” This is a small, explainable knowledge-inference step, not general human-like understanding.

When local knowledge cannot answer an information request, `web_knowledge.py` sends cleaned search terms to Wikipedia’s public search API and returns a page excerpt with a clickable source URL. Results are cached locally in `ven_web_cache.json` for seven days. Web fallback needs an internet connection; if the request fails, VEN reports that Wikipedia could not be reached. The cache and learned facts are local development data and should not be committed. Answers depend on what the parser can represent and may be limited for ambiguous or complex language. Web retrieval does not make the device's speech-recognition provider offline.

## Troubleshooting

- **The app says it cannot connect:** confirm the API is running, then check `API_URL`. A phone cannot use the developer computer’s `127.0.0.1`; use its LAN IP instead.
- **The API starts but vocabulary lookup fails:** confirm `BACKEND/vocabulary.json` exists and contains a JSON list.
- **The microphone does not start:** grant microphone and speech-recognition permissions, confirm the platform has a recognition service, and try a development build if the native module is missing.
- **The web app cannot call the API:** configure CORS on the backend for the frontend’s development origin.
- **Vocabulary generation reports missing NLTK data:** download `wordnet` and `omw-1.4` into the same Python environment used to run the builder.
