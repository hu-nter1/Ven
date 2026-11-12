
import { StyleSheet, View } from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';

export function VenSkyBackground() {
  const player = useVideoPlayer(
    require('../../assets/ven.mp4'),
    (player) => {
      player.loop = true;
      player.muted = true;
      player.audioMixingMode = 'mixWithOthers';
      player.play();
    }
  );

  return (
    <View pointerEvents="none" style={styles.container}>
      <VideoView
        player={player}
        style={styles.video}
        contentFit="cover"
        nativeControls={false}
        fullscreenOptions={{ enable: false }}
        allowsPictureInPicture={false}
        surfaceType="textureView"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    ...StyleSheet.absoluteFill,
    overflow: 'hidden',
    backgroundColor: '#87CEEB',
  },

  video: {
    width: '100%',
    height: '100%',
  },
});
