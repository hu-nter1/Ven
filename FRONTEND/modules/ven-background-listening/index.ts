import { PermissionsAndroid, Platform } from 'react-native';
import { requireNativeModule } from 'expo-modules-core';

type VenBackgroundListeningNativeModule = {
  start(): void;
  stop(): void;
};

const nativeModule =
  Platform.OS === 'android'
    ? requireNativeModule<VenBackgroundListeningNativeModule>(
        'VenBackgroundListening'
      )
    : null;

export async function startVenBackgroundListening() {
  if (Platform.OS !== 'android' || !nativeModule) return;

  if (
    Number(Platform.Version) >= 33 &&
    (await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS,
      {
        title: 'Allow VEN listening notification',
        message:
          'VEN uses an ongoing notification while voice listening is active.',
        buttonPositive: 'Allow',
        buttonNegative: 'Cancel',
      }
    )) !== PermissionsAndroid.RESULTS.GRANTED
  ) {
    throw new Error('Notification permission is required for background listening.');
  }

  nativeModule.start();
}

export function stopVenBackgroundListening() {
  nativeModule?.stop();
}
