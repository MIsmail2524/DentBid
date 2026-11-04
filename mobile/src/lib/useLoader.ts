import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

/** Loads data on focus; `reload` refreshes without clearing what is shown. */
export function useLoader<T>(fn: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [refreshing, setRefreshing] = useState(false);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const reload = useCallback(async () => {
    setRefreshing(true);
    try {
      setData(await fnRef.current());
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => {
    reload();
  }, [reload]));

  return { data, error, refreshing, reload };
}
