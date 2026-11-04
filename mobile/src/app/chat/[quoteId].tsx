import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Text, TextInput, View } from 'react-native';

import { radius, useTheme } from '../../components/theme';
import { Button, ErrorText } from '../../components/ui';
import { useLocale } from '../../i18n';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { useRealtime } from '../../lib/realtime';
import type { Message } from '../../lib/types';

export default function Chat() {
  const t = useTheme();
  const { t: tr } = useLocale();
  const { user } = useAuth();
  const { quoteId, title } = useLocalSearchParams<{ quoteId: string; title?: string }>();
  const qid = Number(quoteId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [error, setError] = useState<unknown>(null);
  const list = useRef<FlatList<Message>>(null);

  useEffect(() => {
    api.messages(qid).then(setMessages).catch(setError);
  }, [qid]);

  useRealtime((e) => {
    if (e.type === 'message.new' && e.quote_id === qid && e.message) {
      const m = e.message;
      setMessages((ms) => (ms.some((x) => x.id === m.id) ? ms : [...ms, m]));
    }
  });

  const send = async () => {
    const body = text.trim();
    if (!body) return;
    setText('');
    try {
      const m = await api.sendMessage(qid, body);
      setMessages((ms) => (ms.some((x) => x.id === m.id) ? ms : [...ms, m]));
    } catch (e) {
      setError(e);
      setText(body);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: t.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}>
      <Stack.Screen options={{ title: title || tr('chat') }} />
      <FlatList
        ref={list}
        data={messages}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={{ padding: 16, gap: 8 }}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: true })}
        renderItem={({ item }) => {
          const mine = item.sender_id === user?.id;
          return (
            <View style={{ alignSelf: mine ? 'flex-end' : 'flex-start', maxWidth: '80%', backgroundColor: mine ? t.primary : t.card,
              borderRadius: radius, paddingHorizontal: 12, paddingVertical: 8 }}>
              <Text style={{ color: mine ? '#fff' : t.text, fontSize: 15 }}>{item.body}</Text>
              <Text style={{ color: mine ? '#ffffffaa' : t.muted, fontSize: 11, marginTop: 2 }}>
                {new Date(item.created_at.endsWith('Z') || item.created_at.includes('+') ? item.created_at : item.created_at + 'Z')
                  .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </Text>
            </View>
          );
        }}
      />
      <View style={{ padding: 12, gap: 6, borderTopWidth: 1, borderTopColor: t.border, backgroundColor: t.card }}>
        <ErrorText error={error} />
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <TextInput value={text} onChangeText={setText} onSubmitEditing={send} placeholder="…" placeholderTextColor={t.muted}
            style={{ flex: 1, backgroundColor: t.inputBg, color: t.text, borderRadius: radius, borderWidth: 1, borderColor: t.border, paddingHorizontal: 12 }} />
          <Button title={tr('send')} icon="send" onPress={send} disabled={!text.trim()} />
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}
