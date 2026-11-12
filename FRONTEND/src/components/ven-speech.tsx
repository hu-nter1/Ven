
import { useRef, useState } from 'react';
import {
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type ScrollViewInstance,
  View,
} from 'react-native';

import * as Speech from 'expo-speech';

import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from 'expo-speech-recognition';

import {
  startVenBackgroundListening,
  stopVenBackgroundListening,
} from '../../modules/ven-background-listening';

const API_URL = 'http://192.168.41.1:8000';

type ChatMessage = {
  id: number;
  sender: 'You' | 'VEN';
  text: string;
  source?: {
    title: string;
    url: string;
  };
};

type ChatResponse = {
  reply: string;
  source_title?: string | null;
  source_url?: string | null;
};

export function VenSpeech() {
  const [recognizing, setRecognizing] = useState(false);
  const [listeningEnabled, setListeningEnabled] = useState(false);
  const [message, setMessage] = useState('VEN is ready.');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');

  const keepListening = useRef(false);
  const processing = useRef(false);
  const restarting = useRef(false);
  const restartTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryDelay = useRef(500);
  const speechSequence = useRef(0);
  const speechStartTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messageId = useRef(0);
  const scrollView = useRef<ScrollViewInstance | null>(null);

  const addMessage = (
    sender: 'You' | 'VEN',
    text: string,
    source?: ChatMessage['source']
  ) => {
    messageId.current += 1;

    setMessages(previous => [
      ...previous,
      {
        id: messageId.current,
        sender,
        text,
        source,
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
      restartListening();
    }
  };

  const restartListening = () => {
    if (
      !keepListening.current ||
      processing.current ||
      restartTimer.current !== null
    ) {
      return;
    }

    const delay = retryDelay.current;
    retryDelay.current = Math.min(delay * 2, 8000);
    restartTimer.current = setTimeout(() => {
      restartTimer.current = null;
      restarting.current = false;
      startRecognition();
    }, delay);
  };

  const clearSpeechStartTimeout = () => {
    if (speechStartTimeout.current !== null) {
      clearTimeout(speechStartTimeout.current);
      speechStartTimeout.current = null;
    }
  };

  const finishSpeech = (sequence: number, status: string) => {
    if (sequence !== speechSequence.current) return;

    speechSequence.current += 1;
    clearSpeechStartTimeout();
    processing.current = false;
    setMessage(status);

    if (keepListening.current) {
      restartListening();
    }
  };

  // Voice messages receive spoken responses.
  // Typed messages receive text responses only.
  const sendToBackend = async (
    userMessage: string,
    speakResponse: boolean
  ) => {
    if (processing.current) return;

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

      const data: ChatResponse = await response.json();

      addMessage(
        'VEN',
        data.reply,
        data.source_title && data.source_url
          ? { title: data.source_title, url: data.source_url }
          : undefined
      );

      if (!speakResponse) {
        processing.current = false;

        setMessage(
          keepListening.current
            ? 'VEN is listening...'
            : 'VEN is ready.'
        );

        if (keepListening.current) {
          restartListening();
        }

        return;
      }

      const sequence = ++speechSequence.current;
      let speechStarted = false;
      setMessage('VEN is preparing to speak...');

      try {
        await Speech.stop();

        if (sequence !== speechSequence.current) return;

        Speech.speak(data.reply, {
          language: 'en-US',
          pitch: 0.85,
          rate: 0.85,

          onStart: () => {
            if (sequence !== speechSequence.current) return;

            speechStarted = true;
            clearSpeechStartTimeout();
            setMessage('VEN is speaking...');
          },

          onDone: () => {
            finishSpeech(
              sequence,
              keepListening.current ? 'VEN is listening...' : 'VEN is ready.'
            );
          },

          onStopped: () => {
            finishSpeech(sequence, 'VEN speech stopped.');
          },

          onError: error => {
            console.error('VEN speech error:', error);
            finishSpeech(
              sequence,
              'VEN could not speak. The reply is available in chat.'
            );
          },
        });

        speechStartTimeout.current = setTimeout(() => {
          void Speech.isSpeakingAsync()
            .then(isSpeaking => {
              if (sequence !== speechSequence.current || speechStarted) return;

              if (isSpeaking) {
                speechStarted = true;
                clearSpeechStartTimeout();
                setMessage('VEN is speaking...');
                return;
              }

              finishSpeech(
                sequence,
                'VEN could not speak. The reply is available in chat.'
              );
            })
            .catch(error => {
              console.error('VEN speech status error:', error);
              finishSpeech(
                sequence,
                'VEN could not speak. The reply is available in chat.'
              );
            });
        }, 5000);
      } catch (error) {
        console.error('VEN speech setup error:', error);
        finishSpeech(
          sequence,
          'VEN could not speak. The reply is available in chat.'
        );
      }
    } catch (error) {
      console.log('VEN backend error:', error);

      processing.current = false;
      setMessage('VEN could not connect to Python.');

      if (keepListening.current) {
        restartListening();
      }
    }
  };

  // Typed messages: text response only.
  const sendTypedMessage = () => {
    const text = draft.trim();

    if (!text || processing.current) return;

    setDraft('');
    addMessage('You', text);

    if (keepListening.current) {
      ExpoSpeechRecognitionModule.stop();
    }

    void sendToBackend(text, false);
  };

  useSpeechRecognitionEvent('start', () => {
    restarting.current = false;
    retryDelay.current = 500;
    setRecognizing(true);
    console.log('VEN microphone activated');
    setMessage(
      Platform.OS === 'android'
        ? 'VEN is listening. Background notification is active.'
        : 'VEN is listening...'
    );
  });

  // Voice messages: text and spoken response.
  useSpeechRecognitionEvent('result', event => {
    const spokenWords = event.results[0]?.transcript?.trim();

    if (spokenWords && event.isFinal && !processing.current) {
      addMessage('You', spokenWords);

      ExpoSpeechRecognitionModule.stop();

      void sendToBackend(spokenWords, true);
    }
  });

  useSpeechRecognitionEvent('end', () => {
    setRecognizing(false);
    restarting.current = false;

    if (keepListening.current && !processing.current) {
      restartListening();
    }
  });

  useSpeechRecognitionEvent('error', event => {
    console.log('VEN recognition error:', event);

    setRecognizing(false);
    restarting.current = false;

    if (keepListening.current && !processing.current) {
      setMessage('Speech recognition stopped. Reconnecting...');
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

      await startVenBackgroundListening();
      startRecognition();
    } catch (error) {
      keepListening.current = false;
      setListeningEnabled(false);
      setMessage(
        error instanceof Error
          ? error.message
          : 'Could not start listening.'
      );
      console.error('VEN start error:', error);
      try {
        stopVenBackgroundListening();
      } catch (stopError) {
        console.error('VEN background service stop error:', stopError);
      }
    }
  };

  const stopListening = () => {
    keepListening.current = false;
    processing.current = false;
    restarting.current = false;
    if (restartTimer.current !== null) {
      clearTimeout(restartTimer.current);
      restartTimer.current = null;
    }
    retryDelay.current = 500;
    speechSequence.current += 1;
    clearSpeechStartTimeout();

    setListeningEnabled(false);

    Speech.stop();
    ExpoSpeechRecognitionModule.stop();
    stopVenBackgroundListening();

    setRecognizing(false);
    setMessage('VEN has stopped listening.');
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      {/* Compact VEN header */}
      <View style={styles.header}>
        <View style={styles.identity}>
          <View style={styles.avatarOuter}>
            <View style={styles.avatarInner}>
              <Text style={styles.avatarText}>V</Text>
            </View>
          </View>

          <View style={styles.headerInfo}>
            <Text style={styles.headerName}>VEN</Text>
            <Text style={styles.headerSubtitle}>
              PERSONAL INTELLIGENCE
            </Text>
          </View>
        </View>

        <View style={styles.connection}>
          <View
            style={[
              styles.statusDot,
              {
                backgroundColor: listeningEnabled
                  ? '#00FF9D'
                  : '#687784',
              },
            ]}
          />
          <Text style={styles.connectionText}>
            {recognizing ? 'ACTIVE' : 'READY'}
          </Text>
        </View>
      </View>

      {/* Full available conversation area */}
      <ScrollView
        ref={scrollView}
        style={styles.chatArea}
        contentContainerStyle={styles.chatContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        onContentSizeChange={() =>
          scrollView.current?.scrollToEnd({ animated: true })
        }
      >
        {messages.length === 0 && (
          <View style={styles.welcome}>
            <View style={styles.welcomeOrb}>
              <Text style={styles.welcomeOrbText}>V</Text>
            </View>

            <Text style={styles.welcomeTitle}>
              How can I help?
            </Text>

            <Text style={styles.welcomeDescription}>
              I'm VEN. Ask me anything, share an idea,
              or let's explore something together.
            </Text>

            <View style={styles.suggestion}>
              <Text style={styles.suggestionLabel}>
                START A CONVERSATION
              </Text>
              <Text style={styles.suggestionText}>
                Type a message below or speak to me.
              </Text>
            </View>
          </View>
        )}

        {messages.map(item => (
          <View
            key={item.id}
            style={[
              styles.messageRow,
              item.sender === 'You'
                ? styles.userRow
                : styles.venRow,
            ]}
          >
            {item.sender === 'VEN' && (
              <View style={styles.messageAvatar}>
                <Text style={styles.messageAvatarText}>V</Text>
              </View>
            )}

            <View
              style={[
                styles.messageCard,
                item.sender === 'You'
                  ? styles.userCard
                  : styles.venCard,
              ]}
            >
              <Text
                style={[
                  styles.messageSender,
                  item.sender === 'You'
                    ? styles.userSender
                    : styles.venSender,
                ]}
              >
                {item.sender === 'You' ? 'YOU' : 'VEN'}
              </Text>

              <Text style={styles.messageText}>
                {item.text}
              </Text>

              {item.source && (
                <Text
                  accessibilityRole="link"
                  onPress={() => {
                    const sourceUrl = item.source?.url;
                    if (sourceUrl) {
                      void Linking.openURL(sourceUrl).catch(error => {
                        console.error('Could not open VEN source:', error);
                      });
                    }
                  }}
                  style={styles.sourceLink}
                >
                  Source: {item.source.title}
                </Text>
              )}
            </View>
          </View>
        ))}
      </ScrollView>

      {/* Status */}
      <View style={styles.statusArea}>
        <View style={styles.statusLine} />
        <Text style={styles.statusText}>{message}</Text>
        <View style={styles.statusLine} />
      </View>

      {/* Typing area */}
      <View style={styles.composer}>
        <View style={styles.inputContainer}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder="Message VEN..."
            placeholderTextColor="#718391"
            style={styles.textInput}
            multiline
            maxLength={2000}
            editable={!processing.current}
            returnKeyType="default"
          />

          <Text style={styles.inputHint}>MESSAGE VEN</Text>
        </View>

        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Send message"
          onPress={sendTypedMessage}
          disabled={!draft.trim() || processing.current}
          style={({ pressed }) => [
            styles.sendButton,
            (!draft.trim() || processing.current) &&
              styles.sendButtonDisabled,
            pressed && styles.buttonPressed,
          ]}
        >
          <Text style={styles.sendIcon}>↑</Text>
        </Pressable>
      </View>

      {/* Voice controls */}
      <View style={styles.voiceArea}>
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
            pressed && styles.buttonPressed,
          ]}
        >
          <Text style={styles.micIcon}>
            {listeningEnabled ? '■' : '🎙'}
          </Text>
        </Pressable>

        <Text style={styles.micLabel}>
          {listeningEnabled
            ? 'VOICE LISTENING ACTIVE'
            : 'TAP TO SPEAK TO VEN'}
        </Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    minHeight: 0,
    width: '100%',
    paddingHorizontal: 0,
    paddingTop: 4,
    paddingBottom: 4,
    backgroundColor: 'transparent',
  },

  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 9,
    backgroundColor: 'rgba(5, 20, 32, 0.94)',
    borderBottomWidth: 1,
    borderColor: 'rgba(0, 217, 255, 0.25)',
    marginBottom: 4,
  },

  identity: {
    flexDirection: 'row',
    alignItems: 'center',
  },

  avatarOuter: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#00D9FF',
    backgroundColor: 'rgba(0, 217, 255, 0.12)',
  },

  avatarInner: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#073B4C',
    alignItems: 'center',
    justifyContent: 'center',
  },

  avatarText: {
    color: '#00FFFF',
    fontSize: 17,
    fontWeight: 'bold',
  },

  headerInfo: {
    marginLeft: 10,
  },

  headerName: {
    color: '#FFFFFF',
    fontSize: 17,
    fontWeight: 'bold',
    letterSpacing: 3,
  },

  headerSubtitle: {
    color: '#00D9FF',
    fontSize: 8,
    letterSpacing: 1.3,
    marginTop: 2,
  },

  connection: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 7,
  },

  statusDot: {
    width: 7,
    height: 7,
    borderRadius: 4,
  },

  connectionText: {
    color: '#A9C3D0',
    fontSize: 10,
    letterSpacing: 1,
  },

  chatArea: {
    flex: 1,
    minHeight: 0,
    width: '100%',
    backgroundColor: 'rgba(5, 17, 29, 0.55)',
  },

  chatContent: {
    flexGrow: 1,
    paddingHorizontal: 15,
    paddingTop: 18,
    paddingBottom: 25,
  },

  welcome: {
    flexGrow: 1,
    width: '100%',
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 18,
  },

  welcomeOrb: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: 'rgba(0, 217, 255, 0.09)',
    borderWidth: 1,
    borderColor: '#00D9FF',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },

  welcomeOrbText: {
    color: '#00FFFF',
    fontSize: 30,
    fontWeight: 'bold',
  },

  welcomeTitle: {
    color: '#FFFFFF',
    fontSize: 23,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },

  welcomeDescription: {
    color: '#A9BBC8',
    fontSize: 14,
    lineHeight: 23,
    textAlign: 'center',
    marginTop: 12,
    maxWidth: 290,
  },

  suggestion: {
    width: '100%',
    padding: 15,
    marginTop: 25,
    backgroundColor: 'rgba(0, 217, 255, 0.06)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(0, 217, 255, 0.2)',
  },

  suggestionLabel: {
    color: '#00D9FF',
    fontSize: 10,
    letterSpacing: 1.5,
    fontWeight: 'bold',
  },

  suggestionText: {
    color: '#A9BBC8',
    fontSize: 12,
    marginTop: 7,
  },

  messageRow: {
    width: '100%',
    flexDirection: 'row',
    marginBottom: 18,
    alignItems: 'flex-start',
  },

  userRow: {
    justifyContent: 'flex-end',
  },

  venRow: {
    justifyContent: 'flex-start',
  },

  messageAvatar: {
    width: 29,
    height: 29,
    borderRadius: 15,
    backgroundColor: '#073B4C',
    borderWidth: 1,
    borderColor: '#00D9FF',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
    marginTop: 3,
  },

  messageAvatarText: {
    color: '#00FFFF',
    fontWeight: 'bold',
    fontSize: 14,
  },

  messageCard: {
    maxWidth: '84%',
    padding: 13,
    borderRadius: 14,
    borderWidth: 1,
  },

  userCard: {
    backgroundColor: 'rgba(0, 119, 145, 0.22)',
    borderColor: 'rgba(0, 217, 255, 0.42)',
    borderTopRightRadius: 3,
  },

  venCard: {
    backgroundColor: 'rgba(20, 35, 49, 0.95)',
    borderColor: 'rgba(160, 190, 210, 0.18)',
    borderTopLeftRadius: 3,
  },

  messageSender: {
    fontSize: 9,
    fontWeight: 'bold',
    letterSpacing: 1.5,
    marginBottom: 7,
  },

  userSender: {
    color: '#00D9FF',
    textAlign: 'right',
  },

  venSender: {
    color: '#00FFB3',
  },

  messageText: {
    color: '#E8F1F5',
    fontSize: 15,
    lineHeight: 23,
  },

  sourceLink: {
    color: '#62DDF5',
    fontSize: 12,
    marginTop: 10,
    textDecorationLine: 'underline',
  },

  statusArea: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 7,
    gap: 9,
  },

  statusLine: {
    height: 1,
    width: 22,
    backgroundColor: 'rgba(0, 217, 255, 0.25)',
  },

  statusText: {
    color: '#9CB2C0',
    fontSize: 11,
    letterSpacing: 0.5,
  },

  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 9,
    padding: 9,
    marginHorizontal: 8,
    backgroundColor: 'rgba(5, 20, 32, 0.96)',
    borderWidth: 1,
    borderColor: 'rgba(0, 217, 255, 0.38)',
    borderRadius: 16,
  },

  inputContainer: {
    flex: 1,
    minHeight: 47,
    justifyContent: 'center',
    paddingHorizontal: 9,
  },

  textInput: {
    color: '#FFFFFF',
    fontSize: 15,
    lineHeight: 21,
    maxHeight: 100,
    minHeight: 25,
    paddingVertical: 7,
    textAlignVertical: 'center',
  },

  inputHint: {
    color: '#536E7D',
    fontSize: 8,
    letterSpacing: 1.4,
    marginTop: 2,
  },

  sendButton: {
    width: 43,
    height: 43,
    borderRadius: 12,
    backgroundColor: '#007F9E',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: '#00D9FF',
  },

  sendButtonDisabled: {
    opacity: 0.35,
  },

  sendIcon: {
    color: '#FFFFFF',
    fontSize: 27,
    fontWeight: 'bold',
    marginTop: -3,
  },

  voiceArea: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 9,
    paddingBottom: 5,
    gap: 12,
  },

  micButton: {
    width: 39,
    height: 39,
    borderRadius: 20,
    backgroundColor: '#073B4C',
    borderWidth: 1.5,
    borderColor: '#00D9FF',
    alignItems: 'center',
    justifyContent: 'center',
  },

  micButtonActive: {
    backgroundColor: '#075E54',
    borderColor: '#00FF88',
  },

  micIcon: {
    color: '#FFFFFF',
    fontSize: 18,
  },

  micLabel: {
    color: '#A9C3D0',
    fontSize: 9,
    fontWeight: 'bold',
    letterSpacing: 1.5,
  },

  buttonPressed: {
    transform: [{ scale: 0.94 }],
    opacity: 0.8,
  },
});
