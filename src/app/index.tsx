
import { StyleSheet, Text, View } from 'react-native';

import { VenAvatar } from '@/components/ven-avatar';
import { VenSkyBackground } from '@/components/ven-sky-background';

export default function HomeScreen() {
  return (
    <View style={styles.container}>

      {/* Moving sky */}
      <VenSkyBackground />

      {/* VEN portrait behind the chat */}
      <View
        pointerEvents="none"
        style={styles.portrait}
      >
        <VenAvatar />
      </View>

      {/* Chat and microphone controls */}
      <View style={styles.chatLayer}>
  <View style={{
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    justifyContent: 'center',
    alignItems: 'center',
  }}>
    <Text style={{ color: 'white', fontSize: 24 }}>
      VEN CHAT IS HERE
    </Text>
  </View>
</View>

    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#87CEEB',
    overflow: 'hidden',
  },

  portrait: {
    position: 'absolute',
    width: '90%',
    height: '75%',
    right: -10,
    top: '12%',
    opacity: 0.18,
    zIndex: 1,
    elevation: 1,
  },

chatLayer: {
  ...StyleSheet.absoluteFillObject,
  zIndex: 100,
  elevation: 100,
  backgroundColor: 'rgb(255, 0, 0)',
},
});
