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
   │                                  └── VENBrain + vocabulary.json
   └── response text ◄──────────── reply
          └── expo-speech reads reply aloud
```

The frontend owns speech capture, conversation display, and text-to-speech. The backend is a synchronous, in-process rule-based responder; it does not call an external AI service or store chat history. Vocabulary entries are loaded into memory when the API starts.

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

Run the app on Android, iOS, or web using the Expo CLI. The speech-recognition package depends on native functionality, so the voice workflow may not work in Expo Go; use a development build when the native module is unavailable. The project uses Continuous Native Generation, so configure native behavior through `app.json` and config plugins rather than hand-editing generated `ios/` or `android/` directories.

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

## Backend

### Install and run

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install fastapi "uvicorn[standard]"
cd BACKEND
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API is defined in `main.py`:

- `GET /` — health/status response.
- `POST /chat` — accepts `{"message": "..."}` and returns `{"reply": "..."}`.

For example:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
```

FastAPI’s interactive documentation is available at `http://127.0.0.1:8000/docs`.

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

The `/chat` endpoint takes a string `message` and returns a string `reply`. Request validation is handled by Pydantic. The backend currently has no database, authentication, rate limiting, or CORS middleware. In particular, browser-based frontend requests from a different origin need a CORS policy before the web app can use the API. Speech recognition availability and permissions vary by platform and device.

## Troubleshooting

- **The app says it cannot connect:** confirm the API is running, then check `API_URL`. A phone cannot use the developer computer’s `127.0.0.1`; use its LAN IP instead.
- **The API starts but vocabulary lookup fails:** confirm `BACKEND/vocabulary.json` exists and contains a JSON list.
- **The microphone does not start:** grant microphone and speech-recognition permissions, confirm the platform has a recognition service, and try a development build if the native module is missing.
- **The web app cannot call the API:** configure CORS on the backend for the frontend’s development origin.
- **Vocabulary generation reports missing NLTK data:** download `wordnet` and `omw-1.4` into the same Python environment used to run the builder.
