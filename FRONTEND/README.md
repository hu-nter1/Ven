# VEN Frontend

The Expo client for VEN. It uses Expo Router and React Native and contains the voice conversation UI.

From this directory, install dependencies and start Expo:

```bash
npm ci
npx expo run:android
npx expo start --dev-client
```

The Android foreground listening service and speech-recognition module require a development build; Expo Go does not include them. The chat client’s backend URL is configured as `API_URL` in `src/components/ven-speech.tsx`. Set it to an address reachable from the simulator or device. See the [repository README](../README.md) for a full quick start and the [developer guide](../DEVELOPER_GUIDE.md) for platform-specific URLs, background limitations, architecture, and development checks.
