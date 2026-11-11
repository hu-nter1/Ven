
import { Image, StyleSheet } from 'react-native';

export function VenAvatar() {
  return (
    <Image
      source={require('../../assets/ven.png')}
      style={styles.avatar}
      resizeMode="contain"
    />
  );
}

const styles = StyleSheet.create({
  avatar: {
    width: '100%',
    height: '100%',
  },
});
