# VEN

VEN is a voice-first personal assistant prototype. Its Expo app captures speech, sends the recognized text to a Python API, displays the response, and reads it aloud. The backend currently answers a small set of conversational intents and looks up word information in a local vocabulary.

## What’s in the repository

- `FRONTEND/` — Expo, React Native, and TypeScript app for Android, iOS, and web.
- `BACKEND/` — FastAPI service, conversation logic, and vocabulary data.
- `DEVELOPER_GUIDE.md` — setup details, architecture, development workflow, and troubleshooting.

## Features

- Voice input with a start/stop listening control and microphone permission handling.
- Spoken replies and a scrolling conversation view.
- Basic greetings, thanks, farewells, identity, and help responses.
- Vocabulary lookups for meanings, examples, synonyms, antonyms, and related words.
- Animated visual background and VEN avatar.

The Explore tab is currently template content. The app does not save conversations between launches.

## Run VEN locally

The client and API run as separate processes. Start the API first, then configure the client to use an address reachable from the device running it.

### 1. Start the backend

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install fastapi "uvicorn[standard]"
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
npx expo start
```

Use the Expo CLI to open the app on your target platform. The speech-recognition package uses native functionality; microphone-based conversations may require a development build rather than Expo Go. See the [developer guide](DEVELOPER_GUIDE.md#frontend) for platform notes.

## API at a glance

`POST /chat` accepts a JSON body and returns a reply:

```json
{
  "message": "What does curious mean?"
}
```

```json
{
  "reply": "Curious is an adjective. ..."
}
```

## Contributing

For repository layout, local development, vocabulary maintenance, and checks, see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

## License

See [LICENSE](LICENSE).
