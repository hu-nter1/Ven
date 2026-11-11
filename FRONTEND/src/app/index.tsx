
import { StyleSheet, View } from 'react-native';

import { VenSpeech } from '@/components/ven-speech';
import { VenAvatar } from '@/components/ven-avatar';
import { VenSkyBackground } from '@/components/ven-sky-background';

export default function HomeScreen() {
  return (
    <View style={styles.container}>

      {/* Moving sky */}
      <View style={styles.skyLayer} pointerEvents="none">
        <VenSkyBackground />
      </View>

      {/* VEN portrait behind the chat */}
      <View
        pointerEvents="none"
        style={styles.portrait}
      >
        <VenAvatar />
      </View>

      {/* Full-screen chat and microphone controls */}
      <View style={styles.chatLayer}>
        <VenSpeech />
      </View>

    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    position: 'relative',
    backgroundColor: '#87CEEB',
    overflow: 'hidden',
  },

  skyLayer: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 0,
    elevation: 0,
  },

  portrait: {
    position: 'absolute',
    width: '100%',
    height: '75%',
    top: '12%',
    left: 0,
    opacity: 0.1,
    zIndex: 1,
    elevation: 1,
  },

  chatLayer: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 3,
    elevation: 3,
    opacity: .5,
  },
});
