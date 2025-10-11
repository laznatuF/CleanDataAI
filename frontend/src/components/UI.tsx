// src/components/UI.tsx
import type { PropsWithChildren, JSX } from "react";
export { Toaster as AppToaster, toast as toaster } from "react-hot-toast";

type ButtonProps = JSX.IntrinsicElements["button"] & { className?: string };

export function Button({ className = "", ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={
        "px-3 py-2 rounded border bg-white hover:bg-gray-50 active:bg-gray-100 " +
        "disabled:opacity-50 disabled:pointer-events-none " + className
      }
    />
  );
}

export function Card({
  children,
  className = "",
}: PropsWithChildren<{ className?: string }>) {
  return <div className={"border rounded-lg bg-white " + className}>{children}</div>;
}

export function Badge({
  children,
  className = "",
}: PropsWithChildren<{ className?: string }>) {
  return (
    <span className={"inline-block text-xs px-2 py-0.5 rounded bg-gray-100 border " + className}>
      {children}
    </span>
  );
}

export function ProgressBar({ value = 0 }: { value?: number }) {
  return (
    <div className="h-2 bg-gray-200 rounded">
      <div
        className="h-2 bg-blue-500 rounded"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}
