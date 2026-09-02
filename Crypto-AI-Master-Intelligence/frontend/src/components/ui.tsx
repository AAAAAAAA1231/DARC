import { ReactNode } from "react";

export function Panel({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <section className="rounded-lg border border-[#1e2a44] bg-[#121a2f]/80 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-mono text-sm tracking-wide text-[#3ee0b4]">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Status({ value }: { value?: string | null }) {
  const v = (value || "UNKNOWN").toUpperCase();
  const color =
    v === "OK" || v === "SAFE" || v === "LOW_RISK" || v === "BULL"
      ? "text-[#3ee0b4]"
      : v === "MALICIOUS" || v === "HIGH_RISK" || v === "ERROR"
        ? "text-[#ff5d73]"
        : "text-[#f5c542]";
  return <span className={`font-mono text-xs ${color}`}>{v}</span>;
}

export function Disclaimer({ text }: { text?: string }) {
  return <p className="mt-3 text-xs leading-relaxed text-[#8aa0c2]">{text || "Statistical output, not a certainty."}</p>;
}

export function Button({ children, onClick, disabled }: { children: ReactNode; onClick?: () => void; disabled?: boolean }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="rounded bg-[#3ee0b4] px-3 py-1 text-xs font-semibold text-[#0b1020] disabled:opacity-40"
    >
      {children}
    </button>
  );
}
