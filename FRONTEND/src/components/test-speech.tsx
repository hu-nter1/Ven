
import { View, Button, Text } from 'react-native';
import * as Speech from 'expo-speech';

export default function TestSpeech() {

  const testVoice = async () => {
    try {
      await Speech.stop();

      Speech.speak(
        'Hello. My name is VEN. I can speak.',
        {
          language: 'en-US',
          pitch: 0.85,
          rate: 0.85,

          onStart: () => console.log('VEN SPEECH STARTED'),

          onDone: () => console.log('VEN SPEECH COMPLETED'),

          onStopped: () => console.log('VEN SPEECH STOPPED'),

          onError: (error) => console.log('VEN SPEECH ERROR:', error),
        }
      );

    } catch (error) {
      console.log('VOICE TEST FAILED:', error);
    }
  };

  return (
    <View style={{ flex: 1, justifyContent: 'center', padding: 30 }}>
      <Text>VEN Voice Test</Text>
      <Button title="TEST VEN VOICE" onPress={testVoice} />
    </View>
  );
}
