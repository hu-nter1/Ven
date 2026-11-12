const {
  AndroidConfig,
  createRunOncePlugin,
  withAndroidManifest,
  withPlugins,
} = require('expo/config-plugins');

const SERVICE_NAME =
  'expo.modules.venbackgroundlistening.VenListeningService';

const withVenBackgroundListening = config =>
  withPlugins(config, [
    [
      AndroidConfig.Permissions.withPermissions,
      [
        'android.permission.FOREGROUND_SERVICE',
        'android.permission.FOREGROUND_SERVICE_MICROPHONE',
        'android.permission.POST_NOTIFICATIONS',
      ],
    ],
    config =>
      withAndroidManifest(config, config => {
        const application = config.modResults.manifest.application?.[0];
        if (!application) {
          throw new Error('VEN background service requires an Android application entry.');
        }

        application.service ??= [];
        const existingService = application.service.find(
          service => service.$?.['android:name'] === SERVICE_NAME
        );

        if (!existingService) {
          application.service.push({
            $: {
              'android:name': SERVICE_NAME,
              'android:exported': 'false',
              'android:foregroundServiceType': 'microphone',
              'android:stopWithTask': 'false',
            },
          });
        }

        return config;
      }),
  ]);

module.exports = createRunOncePlugin(
  withVenBackgroundListening,
  'with-ven-background-listening',
  '1.0.0'
);
