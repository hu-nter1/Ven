# VEN

VEN is a voice-first personal assistant prototype. Its Expo app captures speech, sends the recognized text to a Python API, displays the response, and reads it aloud. The backend composes varied local replies from sentence meaning and vocabulary, answers common and learned facts, and can search public web results with a source link.

## What’s in the repository

- `FRONTEND/` — Expo, React Native, and TypeScript app for Android, iOS, and web.
- `BACKEND/` — FastAPI service, conversation logic, and vocabulary data.
- `DEVELOPER_GUIDE.md` — setup details, architecture, development workflow, and troubleshooting.

## Features

- Voice input with a start/stop listening control and microphone permission handling.
- Spoken replies and a scrolling conversation view.
- Time-aware greetings based on the phone's local time, plus thanks, farewells, identity, and help responses.
- Vocabulary lookups for meanings, examples, synonyms, antonyms, and related words.
- Offline answers from built-in common facts and local learning from explicit statements.
- Varied rule-based conversational replies and generated example sentences from vocabulary definitions.
- No-key public web search fallback with citations and a seven-day local result cache.
- Animated visual background that resumes while VEN listens, and VEN avatar.

VEN does not use a hosted generative-AI API or require search API keys. Replies are locally composed using rules and the available vocabulary; this is not open-ended language-model generation. Public web lookup requires internet access and uses search snippets/knowledge results; it cannot reach every page, private sites, or paywalled content. Learned facts and cached results are stored locally by the backend. The Explore tab is currently template content, and the app does not save conversations between launches.

## Run VEN locally

The client and API run as separate processes. Start the API first, then configure the client to use an address reachable from the device running it.

### 1. Start the backend

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install fastapi "uvicorn[standard]" spacy
python -m spacy download en_core_web_sm
cd BACKEND
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The health endpoint is `http://127.0.0.1:8000/`. Interactive API documentation is at `http://127.0.0.1:8000/docs`.

### 2. Configure and start the app

Set `API_URL` in [`FRONTEND/src/components/ven-speech.tsx`](FRONTEND/src/components/ven-speech.tsx) to the backend base URL reachable from your target:

- iOS simulator: `http://127.0.0.1:8000`
- Android emulator: `http://10.0.2.2:8000`
- Physical device: `http://<computer-LAN-IP>:8000` (both devices must be on the same network)

Then run:

```bash
cd FRONTEND
npm ci
npx expo run:android
npx expo start --dev-client
```

VEN's Android background-listening service and speech-recognition package require a development build, not Expo Go. See the [developer guide](DEVELOPER_GUIDE.md#frontend) for platform notes and iOS limitations.

## API at a glance

`POST /chat` accepts a JSON body and returns a reply:

```json
{
  "message": "Tell me about Mars.",
  "local_hour": 13,
  "conversation_history": [
    {"role": "user", "content": "What is Mars?"},
    {"role": "assistant", "content": "Mars is the fourth planet from the Sun."}
  ]
}
```

```json
{
  "reply": "Here's a result from the web: ...",
  "source_title": "Mars",
  "source_url": "https://en.wikipedia.org/wiki/Mars"
}
```

`source_title` and `source_url` contain the cited page for web-backed answers and are `null` for local replies.
The app sends up to eight recent turns so follow-up questions such as “What did you say?” can refer to VEN's last reply; this context is not saved by the backend.

## Contributing

For repository layout, local development, vocabulary maintenance, and checks, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

## License

See [LICENSE](LICENSE).
