import { useEffect, useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';

export function VenSkyBackground({
  isListening,
}: {
  isListening: boolean;
}) {
  const isListeningRef = useRef(isListening);
  const player = useVideoPlayer(
    require('../../assets/ven-android.mp4'),
    player => {
      player.loop = true;
      player.muted = true;
      player.audioMixingMode = 'mixWithOthers';
      player.addListener('playToEnd', () => {
        player.currentTime = 0;
        player.play();
      });
      player.play();
    }
  );

  useEffect(() => {
    isListeningRef.current = isListening;
    if (isListening && !player.playing) {
      player.play();
    }
  }, [isListening, player]);

  useEffect(() => {
    const subscription = player.addListener('playingChange', event => {
      if (!event.isPlaying && isListeningRef.current) {
        player.play();
      }
    });

    return () => subscription.remove();
  }, [player]);

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
