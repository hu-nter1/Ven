
import { Button, StyleSheet, View } from 'react-native';
import * as Speech from 'expo-speech';

export function VenSpeech() {
  const speak = () => {
    Speech.stop();

    Speech.speak('Hello. I am VEN. How can I help you today?', {
      pitch: 0.85,
      rate: 0.85,
    });
  };

  return (
    <View style={styles.container}>
      <Button
        title="Talk to VEN"
        onPress={speak}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    padding: 15,
    alignItems: 'center',
  },
});
