import type { ReactNode } from "react";

export const formInputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-100";

export function FormField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}

export function FormErrorList({
  messages,
  instruction,
}: {
  messages: string[];
  instruction: string;
}) {
  if (messages.length === 0) return null;

  return (
    <div role="alert" className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      <ul className="list-disc space-y-1 pl-4">
        {messages.map((message, index) => <li key={`${index}-${message}`}>{message}</li>)}
      </ul>
      <p className="mt-2 text-xs">{instruction}</p>
    </div>
  );
}
