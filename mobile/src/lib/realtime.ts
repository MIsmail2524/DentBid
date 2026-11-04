import { useEffect, useRef } from 'react';

import { WS_URL } from './config';
import type { RealtimeEvent } from './types';

type Handler = (e: RealtimeEvent) => void;
const handlers = new Set<Handler>();

let socket: WebSocket | null = null;
let currentToken: string | null = null;
let retry = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
let pinger: ReturnType<typeof setInterval> | null = null;

function open() {
  if (!currentToken) return;
  const ws = new WebSocket(`${WS_URL}/ws?token=${encodeURIComponent(currentToken)}`);
  socket = ws;
  ws.onopen = () => {
    retry = 0;
    pinger = setInterval(() => ws.readyState === 1 && ws.send('ping'), 25000);
  };
  ws.onmessage = (m) => {
    if (m.data === 'pong') return;
    try {
      const e = JSON.parse(String(m.data)) as RealtimeEvent;
      handlers.forEach((h) => h(e));
    } catch {
      // ignore malformed frames
    }
  };
  ws.onclose = () => {
    if (pinger) clearInterval(pinger);
    if (socket !== ws || !currentToken) return;
    // exponential backoff up to 30 s
    timer = setTimeout(open, Math.min(30000, 1000 * 2 ** retry++));
  };
}

export function connectRealtime(token: string | null) {
  if (token === currentToken) return;
  currentToken = token;
  if (timer) clearTimeout(timer);
  const old = socket;
  socket = null;
  old?.close();
  if (token) open();
}

/** Subscribe to live events while the component is mounted. */
export function useRealtime(handler: Handler) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const h: Handler = (e) => ref.current(e);
    handlers.add(h);
    return () => {
      handlers.delete(h);
    };
  }, []);
}
