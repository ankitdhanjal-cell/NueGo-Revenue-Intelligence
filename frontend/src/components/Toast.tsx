import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';

type Tone = 'success' | 'error';
interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
}
const ToastContext = createContext<(message: string, tone?: Tone) => void>(() => undefined);

export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((message: string, tone: Tone = 'success') => {
    const id = Date.now() + Math.random();
    setItems((cur) => [...cur, { id, message, tone }]);
    setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), 6000);
  }, []);
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 right-4 z-[60] space-y-2">
        {items.map((t) => (
          <div
            key={t.id}
            role="status"
            className={`rounded-md px-4 py-2 text-sm font-medium text-white shadow-lg ${t.tone === 'success' ? 'bg-brand-700' : 'bg-red-700'}`}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
