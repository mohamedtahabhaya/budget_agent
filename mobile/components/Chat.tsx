import React, { useState, useRef, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Image
} from 'react-native';
import { Audio } from 'expo-av';
import * as ImagePicker from 'expo-image-picker';
import * as FileSystem from 'expo-file-system/legacy';
import { API_URL, DEFAULT_WORKSPACE_ID } from '../config';
import { THEMES, getCommonStyles, ThemeType } from './Theme';

export interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  imageUri?: string;
  isAudio?: boolean;
}

export default function Chat({
  userId,
  theme,
  messages,
  setMessages
}: {
  userId: string;
  theme: ThemeType;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
}) {
  const colors = THEMES[theme];
  const commonStyles = getCommonStyles(colors);
  const styles = getStyles(colors);

  const COLORS = colors;
  const COMMON_STYLES = commonStyles;

  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordDuration, setRecordDuration] = useState(0);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);

  const scrollViewRef = useRef<ScrollView>(null);
  const timerRef = useRef<any>(null);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const isPreparingRef = useRef<boolean>(false);
  const webMediaRecorderRef = useRef<any>(null);
  const webAudioChunksRef = useRef<any[]>([]);

  useEffect(() => {
    async function setupPermissions() {
      if (Platform.OS === 'web') {
        try {
          const stream = await (navigator as any).mediaDevices.getUserMedia({ audio: true });
          stream.getTracks().forEach((track: any) => track.stop());
        } catch (err) {
          console.warn('Microphone permission denied on web:', err);
        }
        return;
      }
      try {
        const { status } = await Audio.requestPermissionsAsync();
        if (status !== 'granted') {
          alert('Microphone permission is required to record audio notes.');
        }
      } catch (err) {
        console.error('Error requesting permissions:', err);
      }
    }
    setupPermissions();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const startRecording = async () => {
    if (recordingRef.current || isPreparingRef.current || webMediaRecorderRef.current) return;
    isPreparingRef.current = true;
    try {
      if (Platform.OS === 'web') {
        const stream = await (navigator as any).mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new (window as any).MediaRecorder(stream);
        webMediaRecorderRef.current = mediaRecorder;
        webAudioChunksRef.current = [];

        mediaRecorder.ondataavailable = (event: any) => {
          if (event.data.size > 0) {
            webAudioChunksRef.current.push(event.data);
          }
        };

        mediaRecorder.start();
        setIsRecording(true);
        setRecordDuration(0);

        timerRef.current = setInterval(() => {
          setRecordDuration(prev => prev + 1);
        }, 1000);
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording: newRecording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );

      recordingRef.current = newRecording;
      setRecording(newRecording);
      setIsRecording(true);
      setRecordDuration(0);

      timerRef.current = setInterval(() => {
        setRecordDuration(prev => prev + 1);
      }, 1000);

    } catch (err) {
      console.error('Failed to start recording:', err);
      alert('Could not access microphone. Make sure permissions are granted.');
    } finally {
      isPreparingRef.current = false;
    }
  };

  const stopRecording = async () => {
    setIsRecording(false);
    if (timerRef.current) clearInterval(timerRef.current);

    if (Platform.OS === 'web') {
      const activeRecorder = webMediaRecorderRef.current;
      if (!activeRecorder) return;

      webMediaRecorderRef.current = null;
      activeRecorder.onstop = async () => {
        try {
          const audioBlob = new Blob(webAudioChunksRef.current, { type: 'audio/m4a' });
          if (audioBlob.size < 100) {
            alert("Recording too short. Please press and hold to record.");
            return;
          }

          const reader = new FileReader();
          reader.onloadend = () => {
            const base64Audio = (reader.result as string).split(',')[1];
            const userMsgId = Date.now().toString();
            setMessages(prev => [
              ...prev,
              { id: userMsgId, sender: 'user', text: '🎤 Voice Note', isAudio: true }
            ]);
            sendPayload({ audio_data: base64Audio });
          };
          reader.readAsDataURL(audioBlob);
        } catch (err) {
          console.error('Failed to process web audio blob:', err);
        } finally {
          if (activeRecorder.stream) {
            activeRecorder.stream.getTracks().forEach((track: any) => track.stop());
          }
        }
      };
      
      activeRecorder.stop();
      return;
    }

    let activeRecording = recordingRef.current;

    // Wait for recording ready
    if (isPreparingRef.current) {
      for (let i = 0; i < 10; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (recordingRef.current) {
          activeRecording = recordingRef.current;
          break;
        }
      }
    }

    if (!activeRecording) {
      return;
    }

    recordingRef.current = null;
    setRecording(null);

    try {
      await activeRecording.stopAndUnloadAsync();
      const uri = activeRecording.getURI();

      if (uri) {
        const base64Audio = await FileSystem.readAsStringAsync(uri, {
          encoding: FileSystem.EncodingType.Base64,
        });

        const userMsgId = Date.now().toString();
        setMessages(prev => [
          ...prev,
          { id: userMsgId, sender: 'user', text: '🎤 Voice Note', isAudio: true }
        ]);

        sendPayload({ audio_data: base64Audio });
      }
    } catch (err: any) {
      console.error('Failed to stop recording:', err);
      if (err.message && err.message.includes("no valid audio data")) {
        alert("Recording too short. Please press and hold to record.");
      }
    }
  };

  const pickImage = async () => {
    const permissionResult = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permissionResult.granted) {
      alert('Permission to access camera roll is required!');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      quality: 0.5,
    });

    if (!result.canceled && result.assets && result.assets[0].uri) {
      setSelectedImage(result.assets[0].uri);
    }
  };

  const handleSendText = () => {
    if (!inputText.trim() && !selectedImage) return;

    const userMsgId = Date.now().toString();
    const text = inputText;
    const img = selectedImage || undefined;

    setMessages(prev => [
      ...prev,
      { id: userMsgId, sender: 'user', text: text || 'Uploaded an image', imageUri: img }
    ]);

    setInputText('');
    setSelectedImage(null);
    setSending(true);

    if (img) {
      const readImgPromise = Platform.OS === 'web'
        ? fetch(img)
            .then(res => res.blob())
            .then(blob => new Promise<string>((resolve, reject) => {
              const reader = new FileReader();
              reader.onloadend = () => {
                const base64data = reader.result as string;
                const base64 = base64data.split(',')[1];
                resolve(base64);
              };
              reader.onerror = () => reject(new Error('Failed to convert blob to base64'));
              reader.readAsDataURL(blob);
            }))
        : FileSystem.readAsStringAsync(img, {
            encoding: FileSystem.EncodingType.Base64,
          });

      readImgPromise
        .then(base64Img => {
          sendPayload({ message: text, image_data: base64Img });
        })
        .catch(err => {
          console.error("Failed to read image file:", err);
          setSending(false);
          setMessages(prev => [
            ...prev,
            { id: Date.now().toString(), sender: 'agent', text: `⚠️ Failed to read the selected image: ${err.message || err}` }
          ]);
        });
    } else {
      sendPayload({ message: text });
    }
  };

  const sendPayload = async (payload: { message?: string; image_data?: string; audio_data?: string }) => {
    setSending(true);
    const agentMsgId = (Date.now() + 1).toString();

    // Create a blank placeholder for the agent's streaming response
    setMessages(prev => [
      ...prev,
      { id: agentMsgId, sender: 'agent', text: '' }
    ]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: payload.message || '',
          session_id: 'mobile_session',
          user_id: userId,
          workspace_id: DEFAULT_WORKSPACE_ID,
          image_data: payload.image_data,
          audio_data: payload.audio_data
        }),
      });

      let reader;
      let decoder;
      try {
        if (!response.body || typeof (global as any).TextDecoder === 'undefined') {
          throw new Error('Streaming not supported in this environment');
        }
        reader = response.body.getReader();
        decoder = new (global as any).TextDecoder();
      } catch (e) {
        // Hermès streaming fallback
        try {
          const rawText = await response.text();
          const lines = rawText.split('\n');
          let agentText = '';
          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith('data:')) {
              try {
                const jsonStr = trimmed.slice(5).trim();
                const parsed = JSON.parse(jsonStr);
                if (parsed.type === 'token' && parsed.content) {
                  agentText += parsed.content;
                } else if (parsed.type === 'error' && parsed.content) {
                  agentText = `⚠️ Error: ${parsed.content}`;
                }
              } catch (parseErr) {
                // Ignore parse errors for metadata lines
              }
            }
          }
          updateAgentMessage(agentMsgId, agentText || 'No response received.');
        } catch (jsonErr) {
          updateAgentMessage(agentMsgId, 'Error parsing response.');
        }
        setSending(false);
        return;
      }

      let buffer = '';
      let agentText = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep partial line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          // Parse SSE stream format
          if (trimmed.startsWith('data:')) {
            try {
              const jsonStr = trimmed.slice(5).trim();
              const parsed = JSON.parse(jsonStr);
              if (parsed.type === 'token' && parsed.content) {
                agentText += parsed.content;
                updateAgentMessage(agentMsgId, agentText);
              } else if (parsed.type === 'error' && parsed.content) {
                agentText = `⚠️ Error: ${parsed.content}`;
                updateAgentMessage(agentMsgId, agentText);
              }
            } catch (e) {
              // Ignore parse errors for metadata lines
            }
          }
        }
      }
    } catch (error) {
      console.error('Error in chat request:', error);
      updateAgentMessage(agentMsgId, 'Connection error. Make sure your backend API server is running.');
    } finally {
      setSending(false);
    }
  };

  const updateAgentMessage = (id: string, text: string) => {
    setMessages(prev =>
      prev.map(m => (m.id === id ? { ...m, text } : m))
    );
  };

  useEffect(() => {
    // Scroll to bottom on new messages
    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated: true });
    }, 100);
  }, [messages]);

  const formatDuration = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  return (
    <KeyboardAvoidingView
      behavior="padding"
      style={styles.container}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 90 : 50}
    >
      <ScrollView
        ref={scrollViewRef}
        style={styles.chatArea}
        contentContainerStyle={styles.chatContent}
      >
        {messages.map((m) => {
          const isAgent = m.sender === 'agent';
          return (
            <View
              key={m.id}
              style={[
                styles.messageBubble,
                isAgent ? styles.agentBubble : styles.userBubble
              ]}
            >
              {m.imageUri && (
                <Image source={{ uri: m.imageUri }} style={styles.bubbleImage} />
              )}
              <Text style={[styles.messageText, isAgent && { color: colors.text }]}>
                {m.text}
              </Text>
            </View>
          );
        })}
        {sending && messages[messages.length - 1]?.text === '' && (
          <View style={styles.loaderBubble}>
            <ActivityIndicator size="small" color={COLORS.textMuted} />
          </View>
        )}
      </ScrollView>

      {/* Preview selected image */}
      {selectedImage && (
        <View style={styles.previewContainer}>
          <Image source={{ uri: selectedImage }} style={styles.previewImage} />
          <TouchableOpacity style={styles.clearPreview} onPress={() => setSelectedImage(null)}>
            <Text style={styles.clearPreviewText}>✕</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* INPUT CONTROLS */}
      <View style={styles.inputBar}>
        <TouchableOpacity style={styles.clipButton} onPress={pickImage}>
          <Text style={styles.clipIcon}>📎</Text>
        </TouchableOpacity>

        <TextInput
          style={styles.input}
          placeholder="Write your message..."
          placeholderTextColor={COLORS.textMuted}
          value={inputText}
          onChangeText={setInputText}
          editable={!sending && !isRecording}
          onSubmitEditing={handleSendText}
          blurOnSubmit={false}
        />

        {inputText.trim() || selectedImage ? (
          <TouchableOpacity style={styles.sendButton} onPress={handleSendText}>
            <Text style={styles.sendIcon}>🚀</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={[styles.micButton, isRecording && styles.micActiveButton]}
            onPress={isRecording ? stopRecording : startRecording}
          >
            <Text style={styles.micIcon}>{isRecording ? '⏹️' : '🎤'}</Text>
          </TouchableOpacity>
        )}
      </View>
      {isRecording && (
        <View style={styles.recordingOverlay}>
          <Text style={styles.recordingText}>Recording: {formatDuration(recordDuration)}</Text>
          <Text style={styles.recordingSubtext}>Tap mic button again to stop and send</Text>
        </View>
      )}
    </KeyboardAvoidingView>
  );
}

const getStyles = (COLORS: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  chatArea: {
    flex: 1,
  },
  chatContent: {
    padding: 16,
    paddingBottom: 20,
  },
  messageBubble: {
    maxWidth: '80%',
    padding: 12,
    borderRadius: 16,
    marginBottom: 12,
  },
  agentBubble: {
    backgroundColor: COLORS.card,
    borderWidth: 1,
    borderColor: COLORS.border,
    alignSelf: 'flex-start',
    borderTopLeftRadius: 4,
  },
  userBubble: {
    backgroundColor: COLORS.primary,
    alignSelf: 'flex-end',
    borderTopRightRadius: 4,
  },
  messageText: {
    color: '#ffffff',
    fontSize: 14,
    lineHeight: 20,
  },
  loaderBubble: {
    alignSelf: 'flex-start',
    padding: 12,
    marginBottom: 12,
  },
  bubbleImage: {
    width: 200,
    height: 150,
    borderRadius: 8,
    marginBottom: 6,
    resizeMode: 'cover',
  },
  previewContainer: {
    flexDirection: 'row',
    backgroundColor: COLORS.card,
    padding: 8,
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
  },
  previewImage: {
    width: 50,
    height: 50,
    borderRadius: 6,
  },
  clearPreview: {
    marginLeft: 'auto',
    backgroundColor: COLORS.cardSecondary,
    width: 24,
    height: 24,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
  },
  clearPreviewText: {
    color: COLORS.text,
    fontSize: 12,
  },
  inputBar: {
    flexDirection: 'row',
    padding: 12,
    backgroundColor: COLORS.card,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    alignItems: 'center',
  },
  clipButton: {
    padding: 8,
    marginRight: 8,
  },
  clipIcon: {
    fontSize: 20,
    color: COLORS.textMuted,
  },
  input: {
    flex: 1,
    backgroundColor: COLORS.cardSecondary,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 24,
    color: COLORS.text,
    paddingHorizontal: 16,
    paddingVertical: 8,
    fontSize: 14,
  },
  sendButton: {
    marginLeft: 8,
    backgroundColor: COLORS.primary,
    width: 38,
    height: 38,
    borderRadius: 19,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendIcon: {
    fontSize: 16,
  },
  micButton: {
    marginLeft: 8,
    backgroundColor: COLORS.cardSecondary,
    width: 38,
    height: 38,
    borderRadius: 19,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  micActiveButton: {
    backgroundColor: COLORS.danger,
    borderColor: COLORS.danger,
  },
  micIcon: {
    fontSize: 16,
  },
  recordingOverlay: {
    position: 'absolute',
    bottom: 80,
    left: '10%',
    right: '10%',
    backgroundColor: 'rgba(239, 68, 68, 0.9)',
    borderRadius: 20,
    padding: 12,
    alignItems: 'center',
  },
  recordingText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 14,
  },
  recordingSubtext: {
    color: '#fee2e2',
    fontSize: 10,
    marginTop: 2,
  },
});
