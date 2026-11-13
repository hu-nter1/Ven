
import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Linking,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type ScrollViewInstance,
  View,
  useWindowDimensions,
} from 'react-native';

import * as Speech from 'expo-speech';
import AsyncStorage from '@react-native-async-storage/async-storage';

import {
  ExpoSpeechRecognitionModule,
  useSpeechRecognitionEvent,
} from 'expo-speech-recognition';

import {
  startVenBackgroundListening,
  stopVenBackgroundListening,
} from '../../modules/ven-background-listening';

const API_URL = 'http://192.168.41.1:8000';
const RECENT_CHATS_KEY = 'ven.recent-chats.v1';

type ChatMessage = {
  id: number;
  sender: 'You' | 'VEN';
  text: string;
  source?: {
    title: string;
    url: string;
  };
};

type RecentChat = {
  id: string;
  title: string;
  messages: ChatMessage[];
  updatedAt: number;
};

type MemoryFact = {
  subject?: string;
  relation?: string;
  action?: string;
  object?: string | null;
  negation?: boolean;
  modality?: string | null;
  source?: string;
  original_sentence?: string;
};

type ChatResponse = {
  reply: string;
  source_title?: string | null;
  source_url?: string | null;
};

export function VenSpeech({
  onListeningChange,
}: {
  onListeningChange: (enabled: boolean) => void;
}) {
  const [recognizing, setRecognizing] = useState(false);
  const [listeningEnabled, setListeningEnabled] = useState(false);
  const [message, setMessage] = useState('VEN is ready.');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [chatDrawerVisible, setChatDrawerVisible] = useState(false);
  const [recentChats, setRecentChats] = useState<RecentChat[]>([]);
  const [chatsLoaded, setChatsLoaded] = useState(false);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [memoryVisible, setMemoryVisible] = useState(false);
  const [memoryFacts, setMemoryFacts] = useState<MemoryFact[]>([]);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [memoryDeleting, setMemoryDeleting] = useState<number | null>(null);
  const { width } = useWindowDimensions();
  const wideLayout = width >= 760;

  const keepListening = useRef(false);
  const processing = useRef(false);
  const restarting = useRef(false);
  const restartTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryDelay = useRef(500);
  const speechSequence = useRef(0);
  const speechStartTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messageId = useRef(0);
  const newConversation = useRef(true);
  const scrollView = useRef<ScrollViewInstance | null>(null);
  const recentChatsRef = useRef<RecentChat[]>([]);
  const activeChatIdRef = useRef<string | null>(null);
  const memoryDeleteInProgress = useRef(false);

  useEffect(() => {
    let cancelled = false;

    void AsyncStorage.getItem(RECENT_CHATS_KEY)
      .then(saved => {
        if (cancelled) return;

        const parsed: unknown = saved ? JSON.parse(saved) : [];
        if (!Array.isArray(parsed)) {
          throw new Error('Saved recent chats have an invalid format.');
        }

        const restored = parsed.filter(
          (chat): chat is RecentChat =>
            typeof chat?.id === 'string' &&
            typeof chat?.title === 'string' &&
            Array.isArray(chat?.messages) &&
            typeof chat?.updatedAt === 'number'
        );
        recentChatsRef.current = restored;
        setRecentChats(restored);

        const latest = restored[0];
        if (latest) {
          activeChatIdRef.current = latest.id;
          setActiveChatId(latest.id);
          setMessages(latest.messages);
          messageId.current = latest.messages.reduce(
            (largest, item) => Math.max(largest, item.id),
            0
          );
          newConversation.current = false;
        }
        setChatsLoaded(true);
      })
      .catch(error => {
        if (cancelled) return;
        console.error('Could not load VEN recent chats:', error);
        setMessage('Could not load recent chats from this device.');
        setChatsLoaded(true);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    activeChatIdRef.current = activeChatId;
  }, [activeChatId]);

  useEffect(() => {
    if (!chatsLoaded || messages.length === 0) return;

    const activeId = activeChatIdRef.current;
    const chatId = activeId ?? `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const previous = recentChatsRef.current.find(chat => chat.id === chatId);
    const firstUserMessage = messages.find(item => item.sender === 'You');
    const updatedChat: RecentChat = {
      id: chatId,
      title: previous?.title ?? firstUserMessage?.text.slice(0, 48) ?? 'New chat',
      messages,
      updatedAt: Date.now(),
    };
    const nextChats = [
      updatedChat,
      ...recentChatsRef.current.filter(chat => chat.id !== chatId),
    ].slice(0, 50);

    if (!activeId) {
      activeChatIdRef.current = chatId;
      setActiveChatId(chatId);
    }
    recentChatsRef.current = nextChats;
    setRecentChats(nextChats);

    void AsyncStorage.setItem(
      RECENT_CHATS_KEY,
      JSON.stringify(nextChats)
    ).catch(error => {
      console.error('Could not save VEN recent chats:', error);
      setMessage('Could not save recent chats on this device.');
    });
  }, [chatsLoaded, messages]);

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
          local_hour: new Date().getHours(),
          new_conversation: newConversation.current,
          conversation_history: messages.slice(-8).map(item => ({
            role: item.sender === 'You' ? 'user' : 'assistant',
            content: item.text,
          })),
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data: ChatResponse = await response.json();
      newConversation.current = false;

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

    if (!chatsLoaded) {
      setMessage('Loading recent chats...');
      return;
    }
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
    if (!chatsLoaded) {
      setMessage('Loading recent chats...');
      return;
    }

    try {
      processing.current = false;
      keepListening.current = true;

      setListeningEnabled(true);
      onListeningChange(true);
      setMessage('Checking speech recognition...');

      if (!ExpoSpeechRecognitionModule.isRecognitionAvailable()) {
        keepListening.current = false;
        setListeningEnabled(false);
        onListeningChange(false);
        setMessage('Speech recognition is unavailable.');
        return;
      }

      const permission =
        await ExpoSpeechRecognitionModule.requestPermissionsAsync();

      if (!permission.granted) {
        keepListening.current = false;
        setListeningEnabled(false);
        onListeningChange(false);
        setMessage('Microphone permission denied.');
        return;
      }

      await startVenBackgroundListening();
      startRecognition();
    } catch (error) {
      keepListening.current = false;
      setListeningEnabled(false);
      onListeningChange(false);
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
    onListeningChange(false);

    Speech.stop();
    ExpoSpeechRecognitionModule.stop();
    stopVenBackgroundListening();

    setRecognizing(false);
    setMessage('VEN has stopped listening.');
  };

  const clearCurrentChat = (action: 'new' | 'delete') => {
    if (processing.current) {
      Alert.alert(
        'VEN is still responding',
        'Wait for the current response to finish before changing chats.'
      );
      return;
    }

    const clear = () => {
      setChatDrawerVisible(false);
      speechSequence.current += 1;
      clearSpeechStartTimeout();
      void Speech.stop();
      setMessages([]);
      setDraft('');
      messageId.current = 0;
      const currentChatId = activeChatIdRef.current;
      if (action === 'delete' && currentChatId) {
        const remaining = recentChatsRef.current.filter(
          chat => chat.id !== currentChatId
        );
        recentChatsRef.current = remaining;
        setRecentChats(remaining);
        void AsyncStorage.setItem(
          RECENT_CHATS_KEY,
          JSON.stringify(remaining)
        ).catch(error => {
          console.error('Could not delete VEN recent chat:', error);
          setMessage('Could not delete this chat from this device.');
        });
      }
      activeChatIdRef.current = null;
      setActiveChatId(null);
      newConversation.current = true;
      setMessage(
        keepListening.current
          ? 'VEN is listening...'
          : 'VEN is ready.'
      );
    };

    if (messages.length === 0) {
      clear();
      return;
    }

    const isNewChat = action === 'new';
    const title = isNewChat ? 'Start a new chat?' : 'Delete this chat?';
    const description = isNewChat
      ? 'Your current conversation will remain in Recent Chats.'
      : 'This conversation will be removed from this device.';
    if (Platform.OS === 'web') {
      if (typeof window !== 'undefined' && window.confirm(`${title}\n\n${description}`)) {
        clear();
      }
      return;
    }

    Alert.alert(
      title,
      description,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: isNewChat ? 'New chat' : 'Delete chat',
          style: 'destructive',
          onPress: clear,
        },
      ]
    );
  };

  const selectRecentChat = (chat: RecentChat) => {
    if (processing.current || !chatsLoaded) return;

    activeChatIdRef.current = chat.id;
    setActiveChatId(chat.id);
    setMessages(chat.messages);
    messageId.current = chat.messages.reduce(
      (largest, item) => Math.max(largest, item.id),
      0
    );
    newConversation.current = false;
    setDraft('');
    setChatDrawerVisible(false);
    setMessage(keepListening.current ? 'VEN is listening...' : 'VEN is ready.');
  };

  const openMemory = async () => {
    setChatDrawerVisible(false);
    setMemoryVisible(true);
    setMemoryLoading(true);
    setMemoryError(null);
    try {
      const response = await fetch(`${API_URL}/memory`);
      if (!response.ok) {
        throw new Error(`Memory request failed with status ${response.status}`);
      }
      const data: { facts?: MemoryFact[] } = await response.json();
      if (!Array.isArray(data.facts)) {
        throw new Error('Memory response was not a list of facts.');
      }
      setMemoryFacts(data.facts);
    } catch (error) {
      console.error('Could not load VEN memory:', error);
      setMemoryError('Could not load VEN’s learned facts. Check the backend connection.');
    } finally {
      setMemoryLoading(false);
    }
  };

  const forgetMemory = async (factIndex: number) => {
    const forget = async () => {
      if (memoryDeleteInProgress.current) return;
      memoryDeleteInProgress.current = true;
      setMemoryDeleting(factIndex);
      try {
        const response = await fetch(`${API_URL}/memory/${factIndex}`, {
          method: 'DELETE',
        });
        if (!response.ok) {
          throw new Error(`Memory delete failed with status ${response.status}`);
        }
        const data: { facts?: MemoryFact[] } = await response.json();
        if (!Array.isArray(data.facts)) {
          throw new Error('Memory response was not a list of facts.');
        }
        setMemoryFacts(data.facts);
        setMemoryError(null);
      } catch (error) {
        console.error('Could not forget VEN memory:', error);
        setMemoryError('Could not remove that fact. Please try again.');
      } finally {
        memoryDeleteInProgress.current = false;
        setMemoryDeleting(null);
      }
    };

    if (Platform.OS === 'web') {
      if (typeof window !== 'undefined' && window.confirm('Forget this learned fact?')) {
        await forget();
      }
      return;
    }
    Alert.alert('Forget this fact?', 'VEN will no longer remember it.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Forget', style: 'destructive', onPress: () => void forget() },
    ]);
  };

  const describeFact = (fact: MemoryFact) => {
    if (fact.source || fact.original_sentence) {
      return fact.source ?? fact.original_sentence ?? '';
    }
    const relation = (fact.relation ?? fact.action ?? 'relates to').replaceAll('_', ' ');
    const negation = fact.negation ? 'not ' : '';
    return [fact.subject, negation + relation, fact.object]
      .filter(Boolean)
      .join(' ');
  };

  const composer = (
    <View
      style={[
        styles.composer,
        wideLayout && messages.length === 0 && styles.welcomeComposer,
      ]}
    >
      <View style={styles.inputContainer}>
        <TextInput
          value={draft}
          onChangeText={setDraft}
          placeholder="How can I help you today?"
          placeholderTextColor="#8B8B8B"
          style={[
            styles.textInput,
            wideLayout && messages.length === 0 && styles.welcomeTextInput,
          ]}
          multiline
          maxLength={2000}
          editable={!processing.current && chatsLoaded}
          returnKeyType="default"
        />
        {(!wideLayout || messages.length > 0) && (
          <Text style={styles.inputHint}>MESSAGE VEN</Text>
        )}
      </View>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Send message"
        onPress={sendTypedMessage}
        disabled={!draft.trim() || processing.current || !chatsLoaded}
        style={({ pressed }) => [
          styles.sendButton,
          (!draft.trim() || processing.current || !chatsLoaded) &&
            styles.sendButtonDisabled,
          pressed && styles.buttonPressed,
        ]}
      >
        <Text style={styles.sendIcon}>↑</Text>
      </Pressable>
    </View>
  );

  const statusArea = (
    <View style={styles.statusArea}>
      <View style={styles.statusLine} />
      <Text style={styles.statusText}>{message}</Text>
      <View style={styles.statusLine} />
    </View>
  );

  const voiceArea = (
    <View style={styles.voiceArea}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{
          disabled: !listeningEnabled && !chatsLoaded,
        }}
        disabled={!listeningEnabled && !chatsLoaded}
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
          !listeningEnabled && !chatsLoaded && styles.drawerActionDisabled,
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
  );

  return (
    <KeyboardAvoidingView
      style={[styles.container, wideLayout && styles.wideContainer]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <>
        <View style={[styles.appShell, wideLayout && styles.wideAppShell]}>
          {wideLayout && (
            <View style={styles.sidebar}>
              <View style={styles.sidebarBrand}>
                <Text style={styles.sidebarBrandText}>VEN</Text>
              </View>

              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Start a new chat"
                accessibilityState={{ disabled: !chatsLoaded }}
                onPress={() => clearCurrentChat('new')}
                disabled={!chatsLoaded}
                style={({ pressed }) => [
                  styles.sidebarAction,
                  !chatsLoaded && styles.drawerActionDisabled,
                  pressed && styles.buttonPressed,
                ]}
              >
                <Text style={styles.sidebarNewIcon}>+</Text>
                <Text style={styles.sidebarActionText}>New chat</Text>
              </Pressable>

              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Delete current chat"
                accessibilityState={{ disabled: messages.length === 0 || !chatsLoaded }}
                disabled={messages.length === 0 || !chatsLoaded}
                onPress={() => clearCurrentChat('delete')}
                style={({ pressed }) => [
                  styles.sidebarAction,
                  styles.sidebarDeleteAction,
                  messages.length === 0 && styles.drawerActionDisabled,
                  pressed && styles.buttonPressed,
                ]}
              >
                <Text style={styles.sidebarDeleteIcon}>×</Text>
                <Text style={styles.sidebarActionText}>Delete chat</Text>
              </Pressable>

              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Open memory"
                onPress={() => void openMemory()}
                style={({ pressed }) => [
                  styles.sidebarAction,
                  pressed && styles.buttonPressed,
                ]}
              >
                <Text style={styles.sidebarMemoryIcon}>✦</Text>
                <Text style={styles.sidebarActionText}>Memory</Text>
              </Pressable>

              <Text style={styles.sidebarSectionTitle}>RECENT CHATS</Text>
              <ScrollView
                style={styles.sidebarChatList}
                contentContainerStyle={styles.sidebarChatListContent}
                showsVerticalScrollIndicator={false}
              >
                {recentChats.length === 0 ? (
                  <Text style={styles.sidebarEmpty}>Your chats will appear here.</Text>
                ) : (
                  recentChats.map(chat => (
                    <Pressable
                      key={chat.id}
                      accessibilityRole="button"
                      accessibilityLabel={`Open chat: ${chat.title}`}
                      accessibilityState={{
                        selected: activeChatId === chat.id,
                        disabled: !chatsLoaded,
                      }}
                      onPress={() => selectRecentChat(chat)}
                      disabled={!chatsLoaded}
                      style={({ pressed }) => [
                        styles.sidebarChat,
                        activeChatId === chat.id && styles.sidebarChatSelected,
                        pressed && styles.buttonPressed,
                      ]}
                    >
                      <Text numberOfLines={1} style={styles.sidebarChatTitle}>
                        {chat.title}
                      </Text>
                    </Pressable>
                  ))
                )}
              </ScrollView>

              <View style={styles.sidebarBottom}>
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
                <Text style={styles.sidebarNote}>
                  Chats are saved on this device.
                </Text>
              </View>
            </View>
          )}

          <View style={styles.mainPane}>
            {!wideLayout && (
              <View style={styles.header}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Open chat menu"
                  accessibilityState={{ expanded: chatDrawerVisible }}
                  onPress={() => setChatDrawerVisible(true)}
                  style={({ pressed }) => [
                    styles.menuButton,
                    pressed && styles.buttonPressed,
                  ]}
                >
                  <Text style={styles.menuIcon}>☰</Text>
                </Pressable>

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

                <View style={styles.headerActions}>
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
              </View>
            )}

            <ScrollView
              ref={scrollView}
              style={[
                styles.chatArea,
                wideLayout && styles.wideChatArea,
              ]}
              contentContainerStyle={[
                styles.chatContent,
                wideLayout && styles.wideChatContent,
              ]}
              showsVerticalScrollIndicator={false}
              keyboardShouldPersistTaps="handled"
              onContentSizeChange={() =>
                scrollView.current?.scrollToEnd({ animated: true })
              }
            >
              {messages.length === 0 && (
                wideLayout ? (
                  <View style={styles.desktopWelcome}>
                    <View style={styles.desktopWelcomeHeading}>
                      <View style={styles.desktopWelcomeMark}>
                        <Text style={styles.desktopWelcomeMarkText}>✳</Text>
                      </View>
                      <Text style={styles.desktopWelcomeTitle}>
                        Let’s talk
                      </Text>
                    </View>
                    {composer}
                    {statusArea}
                    {voiceArea}
                  </View>
                ) : (
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
                )
              )}

              {messages.map(item => (
                <View
                  key={item.id}
                  style={[
                    styles.messageRow,
                    item.sender === 'You'
                      ? styles.userRow
                      : styles.venRow,
                    wideLayout && styles.wideMessageRow,
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

            {(!wideLayout || messages.length > 0) && (
              <View
                style={[
                  styles.chatControls,
                  wideLayout && styles.wideChatControls,
                ]}
              >
                {statusArea}
                {composer}
                {voiceArea}
              </View>
            )}
          </View>
        </View>

        <Modal
        visible={chatDrawerVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setChatDrawerVisible(false)}
      >
        <View style={styles.drawerOverlay}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Close chat menu"
            style={styles.drawerBackdrop}
            onPress={() => setChatDrawerVisible(false)}
          />
          <View
            accessibilityViewIsModal
            style={styles.drawerPanel}
          >
            <View style={styles.drawerHeader}>
              <Text style={styles.drawerTitle}>CHAT MENU</Text>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel="Close chat menu"
                onPress={() => setChatDrawerVisible(false)}
                style={({ pressed }) => [
                  styles.drawerCloseButton,
                  pressed && styles.buttonPressed,
                ]}
              >
                <Text style={styles.drawerCloseIcon}>×</Text>
              </Pressable>
            </View>

            <Text style={styles.drawerDescription}>
              Manage this conversation
            </Text>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Start a new chat"
              accessibilityState={{ disabled: !chatsLoaded }}
              onPress={() => clearCurrentChat('new')}
              disabled={!chatsLoaded}
              style={({ pressed }) => [
                styles.drawerAction,
                !chatsLoaded && styles.drawerActionDisabled,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={styles.drawerActionIcon}>+</Text>
              <View style={styles.drawerActionText}>
                <Text style={styles.drawerActionTitle}>New chat</Text>
                <Text style={styles.drawerActionDescription}>
                  Start a fresh conversation
                </Text>
              </View>
            </Pressable>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Delete current chat"
              accessibilityState={{ disabled: messages.length === 0 || !chatsLoaded }}
              disabled={messages.length === 0 || !chatsLoaded}
              onPress={() => clearCurrentChat('delete')}
              style={({ pressed }) => [
                styles.drawerAction,
                styles.drawerDeleteAction,
                messages.length === 0 && styles.drawerActionDisabled,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={styles.drawerDeleteIcon}>×</Text>
              <View style={styles.drawerActionText}>
                <Text style={styles.drawerDeleteTitle}>Delete chat</Text>
                <Text style={styles.drawerActionDescription}>
                  Clear this conversation
                </Text>
              </View>
            </Pressable>

            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Open memory"
              onPress={() => void openMemory()}
              style={({ pressed }) => [
                styles.drawerAction,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={styles.drawerActionIcon}>✦</Text>
              <View style={styles.drawerActionText}>
                <Text style={styles.drawerActionTitle}>Memory</Text>
                <Text style={styles.drawerActionDescription}>
                  Review or forget learned facts
                </Text>
              </View>
            </Pressable>

            <Text style={styles.drawerSectionTitle}>RECENT CHATS</Text>
            <ScrollView
              style={styles.drawerChatList}
              contentContainerStyle={styles.drawerChatListContent}
              showsVerticalScrollIndicator={false}
            >
              {recentChats.length === 0 ? (
                <Text style={styles.drawerEmpty}>Your chats will appear here.</Text>
              ) : (
                recentChats.map(chat => (
                  <Pressable
                    key={chat.id}
                    accessibilityRole="button"
                    accessibilityLabel={`Open chat: ${chat.title}`}
                    accessibilityState={{
                      selected: activeChatId === chat.id,
                      disabled: !chatsLoaded,
                    }}
                    onPress={() => selectRecentChat(chat)}
                    disabled={!chatsLoaded}
                    style={({ pressed }) => [
                      styles.drawerChat,
                      activeChatId === chat.id && styles.drawerChatSelected,
                      pressed && styles.buttonPressed,
                    ]}
                  >
                    <Text numberOfLines={1} style={styles.drawerChatTitle}>
                      {chat.title}
                    </Text>
                  </Pressable>
                ))
              )}
            </ScrollView>
          </View>
        </View>
        </Modal>

        <Modal
          visible={memoryVisible}
          transparent
          animationType="fade"
          onRequestClose={() => setMemoryVisible(false)}
        >
          <View style={styles.memoryOverlay}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Close memory"
              style={styles.memoryBackdrop}
              onPress={() => setMemoryVisible(false)}
            />
            <View accessibilityViewIsModal style={styles.memoryPanel}>
              <View style={styles.drawerHeader}>
                <Text style={styles.drawerTitle}>VEN’S MEMORY</Text>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Close memory"
                  onPress={() => setMemoryVisible(false)}
                  style={({ pressed }) => [
                    styles.drawerCloseButton,
                    pressed && styles.buttonPressed,
                  ]}
                >
                  <Text style={styles.drawerCloseIcon}>×</Text>
                </Pressable>
              </View>
              <Text style={styles.memoryDescription}>
                Facts VEN has learned from your conversations.
              </Text>
              {memoryLoading ? (
                <Text style={styles.memoryState}>Loading memory…</Text>
              ) : memoryError ? (
                <Text accessibilityRole="alert" style={styles.memoryError}>
                  {memoryError}
                </Text>
              ) : memoryFacts.length === 0 ? (
                <Text style={styles.memoryState}>VEN has not saved any facts yet.</Text>
              ) : (
                <ScrollView
                  style={styles.memoryFacts}
                  contentContainerStyle={styles.memoryFactsContent}
                  showsVerticalScrollIndicator
                >
                  {memoryFacts.map((fact, index) => (
                    <View key={`${index}-${describeFact(fact)}`} style={styles.memoryFact}>
                      <Text style={styles.memoryFactText}>{describeFact(fact)}</Text>
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={`Forget ${describeFact(fact)}`}
                        onPress={() => void forgetMemory(index)}
                        disabled={memoryDeleting !== null}
                        style={({ pressed }) => [
                          styles.memoryForgetButton,
                          memoryDeleting !== null && styles.drawerActionDisabled,
                          pressed && styles.buttonPressed,
                        ]}
                      >
                        <Text style={styles.memoryForgetText}>
                          {memoryDeleting === index ? 'Forgetting…' : 'Forget'}
                        </Text>
                      </Pressable>
                    </View>
                  ))}
                </ScrollView>
              )}
            </View>
          </View>
        </Modal>
      </>
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

  wideContainer: {
    paddingTop: 0,
    paddingBottom: 0,
  },

  appShell: {
    flex: 1,
    minHeight: 0,
    width: '100%',
  },

  wideAppShell: {
    flexDirection: 'row',
  },

  sidebar: {
    width: 255,
    minHeight: 0,
    paddingHorizontal: 20,
    paddingTop: 22,
    paddingBottom: 20,
    backgroundColor: 'rgba(8, 12, 18, 0.88)',
    borderRightWidth: 1,
    borderColor: 'rgba(210, 225, 238, 0.12)',
  },

  sidebarBrand: {
    height: 54,
    justifyContent: 'center',
    marginBottom: 16,
    paddingHorizontal: 8,
  },

  sidebarBrandText: {
    color: '#F3F7FA',
    fontSize: 26,
    fontWeight: '600',
    letterSpacing: 3,
  },

  sidebarAction: {
    minHeight: 46,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    marginBottom: 9,
    borderRadius: 9,
    backgroundColor: 'rgba(0, 217, 255, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(0, 217, 255, 0.23)',
  },

  sidebarDeleteAction: {
    backgroundColor: 'rgba(255, 88, 104, 0.07)',
    borderColor: 'rgba(255, 115, 128, 0.2)',
  },

  sidebarNewIcon: {
    width: 25,
    color: '#53E6FF',
    fontSize: 23,
    fontWeight: '500',
  },

  sidebarDeleteIcon: {
    width: 25,
    color: '#FF8791',
    fontSize: 23,
  },

  sidebarActionText: {
    color: '#E4EDF2',
    fontSize: 14,
  },

  sidebarMemoryIcon: {
    width: 25,
    color: '#53E6FF',
    fontSize: 18,
  },

  sidebarSectionTitle: {
    color: '#8195A2',
    fontSize: 10,
    letterSpacing: 1.2,
    marginTop: 16,
    marginBottom: 8,
    paddingHorizontal: 8,
  },

  sidebarChatList: {
    flex: 1,
    minHeight: 0,
  },

  sidebarChatListContent: {
    paddingBottom: 8,
  },

  sidebarChat: {
    minHeight: 38,
    justifyContent: 'center',
    paddingHorizontal: 10,
    borderRadius: 7,
  },

  sidebarChatSelected: {
    backgroundColor: 'rgba(0, 217, 255, 0.12)',
  },

  sidebarChatTitle: {
    color: '#CFDCE3',
    fontSize: 12,
  },

  sidebarEmpty: {
    color: '#8195A2',
    fontSize: 12,
    lineHeight: 18,
    paddingHorizontal: 8,
  },

  sidebarBottom: {
    marginTop: 'auto',
    paddingTop: 18,
    borderTopWidth: 1,
    borderColor: 'rgba(210, 225, 238, 0.12)',
  },

  sidebarNote: {
    color: '#8195A2',
    fontSize: 11,
    lineHeight: 17,
    marginTop: 12,
  },

  mainPane: {
    flex: 1,
    minWidth: 0,
    minHeight: 0,
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

  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },

  menuButton: {
    width: 36,
    height: 36,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(0, 217, 255, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(0, 217, 255, 0.4)',
  },

  menuIcon: {
    color: '#00D9FF',
    fontSize: 18,
  },

  drawerOverlay: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: 'rgba(0, 0, 0, 0.58)',
  },

  drawerBackdrop: {
    ...StyleSheet.absoluteFill,
  },

  drawerPanel: {
    width: 290,
    maxWidth: '84%',
    height: '100%',
    paddingHorizontal: 18,
    paddingTop: 22,
    backgroundColor: '#071A28',
    borderRightWidth: 1,
    borderColor: 'rgba(0, 217, 255, 0.35)',
    elevation: 18,
  },

  drawerHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },

  drawerTitle: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: 'bold',
    letterSpacing: 1.5,
  },

  drawerCloseButton: {
    width: 34,
    height: 34,
    borderRadius: 17,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
  },

  drawerCloseIcon: {
    color: '#C4D6E0',
    fontSize: 23,
    lineHeight: 25,
  },

  drawerDescription: {
    color: '#8EA7B5',
    fontSize: 12,
    marginTop: 4,
    marginBottom: 22,
  },

  drawerAction: {
    minHeight: 64,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 12,
    marginBottom: 10,
    borderRadius: 12,
    backgroundColor: 'rgba(0, 217, 255, 0.09)',
    borderWidth: 1,
    borderColor: 'rgba(0, 217, 255, 0.3)',
  },

  drawerDeleteAction: {
    backgroundColor: 'rgba(255, 88, 104, 0.08)',
    borderColor: 'rgba(255, 115, 128, 0.3)',
  },

  drawerActionDisabled: {
    opacity: 0.4,
  },

  drawerActionIcon: {
    width: 28,
    color: '#00D9FF',
    fontSize: 24,
    fontWeight: 'bold',
  },

  drawerDeleteIcon: {
    width: 28,
    color: '#FF8791',
    fontSize: 24,
    fontWeight: 'bold',
  },

  drawerActionText: {
    flex: 1,
  },

  drawerActionTitle: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },

  drawerDeleteTitle: {
    color: '#FF9AA3',
    fontSize: 14,
    fontWeight: '600',
  },

  drawerActionDescription: {
    color: '#8EA7B5',
    fontSize: 11,
    marginTop: 4,
  },

  drawerSectionTitle: {
    color: '#8195A2',
    fontSize: 10,
    letterSpacing: 1.2,
    marginTop: 12,
    marginBottom: 6,
  },

  drawerChatList: {
    flex: 1,
    minHeight: 0,
  },

  drawerChatListContent: {
    paddingBottom: 14,
  },

  drawerChat: {
    minHeight: 42,
    justifyContent: 'center',
    paddingHorizontal: 10,
    borderRadius: 8,
  },

  drawerChatSelected: {
    backgroundColor: 'rgba(0, 217, 255, 0.12)',
  },

  drawerChatTitle: {
    color: '#DCE8EE',
    fontSize: 12,
  },

  drawerEmpty: {
    color: '#8EA7B5',
    fontSize: 12,
    lineHeight: 18,
    paddingVertical: 8,
  },

  memoryOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 18,
    backgroundColor: 'rgba(0, 0, 0, 0.62)',
  },

  memoryBackdrop: {
    ...StyleSheet.absoluteFill,
  },

  memoryPanel: {
    width: '100%',
    maxWidth: 520,
    maxHeight: '82%',
    minHeight: 210,
    padding: 20,
    borderRadius: 16,
    backgroundColor: '#071A28',
    borderWidth: 1,
    borderColor: 'rgba(0, 217, 255, 0.35)',
    elevation: 18,
  },

  memoryDescription: {
    color: '#8EA7B5',
    fontSize: 12,
    lineHeight: 18,
    marginTop: 8,
    marginBottom: 10,
  },

  memoryState: {
    color: '#B9C9D1',
    fontSize: 13,
    lineHeight: 20,
    paddingVertical: 18,
  },

  memoryError: {
    color: '#FF9AA3',
    fontSize: 13,
    lineHeight: 20,
    paddingVertical: 18,
  },

  memoryFacts: {
    flexShrink: 1,
  },

  memoryFactsContent: {
    paddingBottom: 8,
  },

  memoryFact: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderColor: 'rgba(210, 225, 238, 0.1)',
  },

  memoryFactText: {
    flex: 1,
    color: '#E4EDF2',
    fontSize: 13,
    lineHeight: 19,
  },

  memoryForgetButton: {
    marginLeft: 12,
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 7,
    backgroundColor: 'rgba(255, 88, 104, 0.12)',
  },

  memoryForgetText: {
    color: '#FF9AA3',
    fontSize: 11,
    fontWeight: '600',
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

  wideChatArea: {
    backgroundColor: 'rgba(14, 16, 20, 0.56)',
  },

  chatContent: {
    flexGrow: 1,
    paddingHorizontal: 15,
    paddingTop: 18,
    paddingBottom: 25,
  },

  wideChatContent: {
    flexGrow: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 42,
    paddingTop: 32,
    paddingBottom: 28,
  },

  desktopWelcome: {
    flexGrow: 1,
    width: '100%',
    maxWidth: 720,
    alignSelf: 'center',
    justifyContent: 'center',
    paddingVertical: 28,
  },

  desktopWelcomeHeading: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 34,
  },

  desktopWelcomeMark: {
    width: 42,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 8,
  },

  desktopWelcomeMarkText: {
    color: '#42DFF5',
    fontSize: 43,
    lineHeight: 48,
  },

  desktopWelcomeTitle: {
    color: '#F2F5F7',
    fontSize: 42,
    fontWeight: '400',
    letterSpacing: -1,
  },

  wideMessageRow: {
    width: '100%',
    maxWidth: 900,
    alignSelf: 'center',
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

  welcomeComposer: {
    minHeight: 112,
    alignItems: 'flex-end',
    padding: 11,
    backgroundColor: 'rgba(37, 40, 45, 0.82)',
    borderColor: 'rgba(220, 232, 240, 0.19)',
    borderRadius: 17,
  },

  chatControls: {
    width: '100%',
  },

  wideChatControls: {
    width: '100%',
    maxWidth: 900,
    alignSelf: 'center',
    paddingHorizontal: 42,
    paddingBottom: 10,
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

  welcomeTextInput: {
    minHeight: 82,
    textAlignVertical: 'top',
    paddingTop: 4,
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
