// src/hooks/useLocalStorage.ts
import { useEffect, useState } from "react";

export default function useLocalStorage<T>(key: string, init: T) {
  const [val, setVal] = useState<T>(() => {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : init;
  });
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(val));
  }, [key, val]);
  return [val, setVal] as const;
}
