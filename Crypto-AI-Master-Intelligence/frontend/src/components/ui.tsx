import { ReactNode } from "react";

export function Panel({ title, children, action, className }: { title: string; children: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <section className={`rounded-lg border p-4 ${className || ""}`} style={{ borderColor: "var(--border)", background: "color-mix(in srgb, var(--panel) 90%, transparent)" }}>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-mono text-sm tracking-wide" style={{ color: "var(--accent)" }}>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

export function Status({ value }: { value?: string | null }) {
  const v = (value || "UNKNOWN").toUpperCase();
  const color =
    v === "OK" || v === "SAFE" || v === "LOW_RISK" || v === "BULL" || v === "NATIVE_PROTOCOL"
      ? "var(--accent)"
      : v === "MALICIOUS" || v === "HIGH_RISK" || v === "ERROR"
        ? "var(--danger)"
        : "#c9a227";
  return <span className="font-mono text-xs" style={{ color }}>{v}</span>;
}

export function Disclaimer({ text }: { text?: string }) {
  return <p className="mt-3 text-xs leading-relaxed" style={{ color: "var(--muted)" }}>{text || "Statistical output, not a certainty."}</p>;
}

export function Button({ children, onClick, disabled }: { children: ReactNode; onClick?: () => void; disabled?: boolean }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className="rounded px-3 py-1 text-xs font-semibold disabled:opacity-40"
      style={{ background: "var(--accent)", color: "#0b1020" }}
    >
      {children}
    </button>
  );
}
