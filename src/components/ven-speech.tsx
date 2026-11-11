
import { useRef, useState } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import * as Speech from 'expo-speech';

import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from 'expo-speech-recognition';

const API_URL = 'http://192.168.41.1:8000';

type ChatMessage = {
  id: number;
  sender: 'You' | 'VEN';
  text: string;
};

export function VenSpeech() {
  const [recognizing, setRecognizing] = useState(false);
  const [listeningEnabled, setListeningEnabled] = useState(false);
  const [message, setMessage] = useState('VEN is ready.');
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const keepListening = useRef(false);
  const processing = useRef(false);
  const restarting = useRef(false);
  const messageId = useRef(0);
  const scrollView = useRef<ScrollView>(null);

  const addMessage = (sender: 'You' | 'VEN', text: string) => {
    messageId.current += 1;

    setMessages(previous => [
      ...previous,
      {
        id: messageId.current,
        sender,
        text,
      },
    ]);
  };

  const startRecognition = () => {
    if (
      !keepListening.current ||
      processing.current ||
      restarting.current
    ) {
      return;
    }

    restarting.current = true;

    try {
      ExpoSpeechRecognitionModule.start({
        lang: 'en-US',
        interimResults: true,
        continuous: true,
        maxAlternatives: 1,
      });
    } catch (error) {
      restarting.current = false;
      console.log('VEN listening error:', error);
      setMessage('Could not start listening.');
    }
  };

  const restartListening = () => {
    if (!keepListening.current || processing.current) {
      return;
    }

    setTimeout(() => {
      restarting.current = false;
      startRecognition();
    }, 500);
  };

  const sendToBackend = async (userMessage: string) => {
    processing.current = true;
    setMessage('VEN is thinking...');

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();

      addMessage('VEN', data.reply);
      setMessage('VEN is speaking...');

      Speech.stop();

      Speech.speak(data.reply, {
        pitch: 0.85,
        rate: 0.85,

        onDone: () => {
          processing.current = false;

          if (keepListening.current) {
            setMessage('VEN is listening...');
            restartListening();
          }
        },

        onError: (error) => {
          console.log('VEN speech error:', error);
          processing.current = false;

          if (keepListening.current) {
            setMessage('VEN is listening...');
            restartListening();
          }
        },
      });

    } catch (error) {
      console.log('VEN backend error:', error);

      processing.current = false;
      setMessage('VEN could not connect to Python.');

      restartListening();
    }
  };

  useSpeechRecognitionEvent('start', () => {
    restarting.current = false;
    setRecognizing(true);
    setMessage('VEN is listening...');
  });

  useSpeechRecognitionEvent('result', (event) => {
    const spokenWords = event.results[0]?.transcript;

    if (spokenWords && event.isFinal && !processing.current) {
      addMessage('You', spokenWords);

      ExpoSpeechRecognitionModule.stop();

      void sendToBackend(spokenWords);
    }
  });

  useSpeechRecognitionEvent('end', () => {
    setRecognizing(false);
    restarting.current = false;

    if (keepListening.current && !processing.current) {
      restartListening();
    }
  });

  useSpeechRecognitionEvent('error', (event) => {
    console.log('VEN recognition error:', event);

    setRecognizing(false);
    restarting.current = false;

    if (keepListening.current && !processing.current) {
      setMessage('VEN is waiting for speech...');
      restartListening();
    }
  });

  const startListening = async () => {
    try {
      processing.current = false;
      keepListening.current = true;
      setListeningEnabled(true);
      setMessage('Checking speech recognition...');

      if (!ExpoSpeechRecognitionModule.isRecognitionAvailable()) {
        keepListening.current = false;
        setListeningEnabled(false);
        setMessage('Speech recognition is unavailable.');
        return;
      }

      const permission =
        await ExpoSpeechRecognitionModule.requestPermissionsAsync();

      if (!permission.granted) {
        keepListening.current = false;
        setListeningEnabled(false);
        setMessage('Microphone permission denied.');
        return;
      }

      startRecognition();

    } catch (error) {
      keepListening.current = false;
      setListeningEnabled(false);
      setMessage('Could not start listening.');
      console.log('VEN start error:', error);
    }
  };

  const stopListening = () => {
    keepListening.current = false;
    processing.current = false;
    restarting.current = false;

    setListeningEnabled(false);

    Speech.stop();
    ExpoSpeechRecognitionModule.stop();

    setRecognizing(false);
    setMessage('VEN has stopped listening.');
  };

  return (
    <View style={styles.container}>

      {/* Chat header */}
      <View style={styles.chatHeader}>
        <View style={styles.avatarCircle}>
          <Text style={styles.avatarText}>V</Text>
        </View>

        <View style={styles.headerInfo}>
          <Text style={styles.headerName}>VEN</Text>

          <Text style={styles.headerStatus}>
            {recognizing
              ? 'Listening...'
              : processing.current
                ? 'Thinking...'
                : 'Personal AI Assistant'}
          </Text>
        </View>

        <View
          style={[
            styles.statusDot,
            {
              backgroundColor: listeningEnabled
                ? '#00FF88'
                : '#777777',
            },
          ]}
        />
      </View>

      {/* Conversation area */}
      <ScrollView
        ref={scrollView}
        style={styles.chatArea}
        contentContainerStyle={styles.chatContent}
        showsVerticalScrollIndicator={false}
        onContentSizeChange={() =>
          scrollView.current?.scrollToEnd({ animated: true })
        }
      >
        {messages.length === 0 && (
          <View style={styles.welcome}>
            <Text style={styles.welcomeTitle}>
              Hello, I'm VEN.
            </Text>

            <Text style={styles.welcomeText}>
              Start listening and let's have a conversation.
            </Text>
          </View>
        )}

        {messages.map((item) => (
          <View
            key={item.id}
            style={[
              styles.messageRow,
              item.sender === 'You'
                ? styles.userRow
                : styles.venRow,
            ]}
          >
            <View
              style={[
                styles.bubble,
                item.sender === 'You'
                  ? styles.userBubble
                  : styles.venBubble,
              ]}
            >
              <Text
                style={[
                  styles.sender,
                  item.sender === 'You'
                    ? styles.userSender
                    : styles.venSender,
                ]}
              >
                {item.sender}
              </Text>

              <Text
                style={[
                  styles.messageText,
                  item.sender === 'You'
                    ? styles.userText
                    : styles.venText,
                ]}
              >
                {item.text}
              </Text>
            </View>
          </View>
        ))}
      </ScrollView>

      {/* Status */}
      <Text style={styles.status}>
        {message}
      </Text>

      {/* Round microphone control */}
      <View style={styles.controls}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={
            listeningEnabled
              ? 'Stop listening'
              : 'Start listening'
          }
          onPress={
            listeningEnabled
              ? stopListening
              : startListening
          }
          style={({ pressed }) => [
            styles.micButton,
            listeningEnabled && styles.micButtonActive,
            pressed && styles.micButtonPressed,
          ]}
        >
          <Text style={styles.micIcon}>
            {listeningEnabled ? '■' : '🎙'}
          </Text>
        </Pressable>

        <Text style={styles.micLabel}>
          {listeningEnabled
            ? 'STOP LISTENING'
            : 'START LISTENING'}
        </Text>
      </View>

    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: '100%',
    flex: 1,
    paddingHorizontal: 12,
    paddingBottom: 10,
    backgroundColor: 'transparent',
  },

  chatHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: 'rgba(11, 25, 38, 0.65)',
    borderRadius: 12,
    marginBottom: 10,
  },

  avatarCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: '#003B42',
    alignItems: 'center',
    justifyContent: 'center',
  },

  avatarText: {
    color: '#00FFFF',
    fontSize: 22,
    fontWeight: 'bold',
  },

  headerInfo: {
    flex: 1,
    marginLeft: 12,
  },

  headerName: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: 'bold',
  },

  headerStatus: {
    color: '#CCCCCC',
    fontSize: 12,
    marginTop: 3,
  },

  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },

  chatArea: {
    flex: 1,
    backgroundColor: 'rgba(11, 20, 26, 0.65)',
    borderRadius: 12,
  },

  chatContent: {
    padding: 12,
    paddingBottom: 20,
  },

  welcome: {
    alignItems: 'center',
    marginTop: 40,
    padding: 20,
  },

  welcomeTitle: {
    color: '#00FFFF',
    fontSize: 20,
    fontWeight: 'bold',
  },

  welcomeText: {
    color: '#FFFFFF',
    fontSize: 14,
    textAlign: 'center',
    marginTop: 8,
  },

  messageRow: {
    width: '100%',
    marginBottom: 12,
    flexDirection: 'row',
  },

  userRow: {
    justifyContent: 'flex-end',
  },

  venRow: {
    justifyContent: 'flex-start',
  },

  bubble: {
    maxWidth: '85%',
    paddingHorizontal: 13,
    paddingVertical: 10,
    borderRadius: 12,
  },

  userBubble: {
    backgroundColor: '#075E54',
    borderTopRightRadius: 3,
  },

  venBubble: {
    backgroundColor: '#202C33',
    borderTopLeftRadius: 3,
  },

  sender: {
    fontSize: 12,
    fontWeight: 'bold',
    marginBottom: 5,
  },

  userSender: {
    color: '#8DE0B4',
  },

  venSender: {
    color: '#00FFFF',
  },

  messageText: {
    fontSize: 15,
    lineHeight: 22,
  },

  userText: {
    color: '#FFFFFF',
  },

  venText: {
    color: '#EAEAEA',
  },

  status: {
    marginVertical: 10,
    fontSize: 13,
    color: '#FFFFFF',
    textAlign: 'center',
  },

  controls: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 12,
  },

  micButton: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: '#073B50',
    borderWidth: 2,
    borderColor: '#00FFFF',
    alignItems: 'center',
    justifyContent: 'center',
    elevation: 12,
    shadowColor: '#00FFFF',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.5,
    shadowRadius: 12,
  },

  micButtonActive: {
    backgroundColor: '#075E54',
    borderColor: '#00FF88',
    shadowColor: '#00FF88',
  },

  micButtonPressed: {
    transform: [{ scale: 0.92 }],
    opacity: 0.8,
  },

  micIcon: {
    color: '#FFFFFF',
    fontSize: 30,
    fontWeight: 'bold',
  },

  micLabel: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: 'bold',
    letterSpacing: 2,
    marginTop: 9,
  },
});
