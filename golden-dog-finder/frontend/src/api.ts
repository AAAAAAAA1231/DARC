import type { ScanResponse } from "./types";

export async function fetchScan(force = false): Promise<ScanResponse> {
  const res = await fetch(`/api/scan${force ? "?force=true" : ""}`);
  if (!res.ok) {
    throw new Error(`扫描失败 ${res.status}`);
  }
  return res.json();
}

export function money(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(n / 1_000).toFixed(1)}k`;
  if (abs >= 1) return `$${n.toFixed(2)}`;
  if (abs >= 0.0001) return `$${n.toFixed(5)}`;
  return `$${n.toExponential(1)}`;
}

export function multiple(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return "—";
  if (n >= 100) return `${n.toFixed(0)}x`;
  if (n >= 10) return `${n.toFixed(1)}x`;
  return `${n.toFixed(2)}x`;
}

export function ageLabel(min: number): string {
  if (min < 1) return `${Math.max(1, Math.round(min * 60))}s`;
  if (min < 60) return `${min.toFixed(0)}m`;
  return `${(min / 60).toFixed(1)}h`;
}

export function shortAddr(addr: string): string {
  if (!addr) return "";
  return addr.slice(0, 4) + "…" + addr.slice(-4);
}

export function dexUrl(chain: string, address: string, pair?: string | null): string {
  if (pair) return `https://dexscreener.com/${chain}/${pair}`;
  return `https://dexscreener.com/${chain}/${address}`;
}

export function keyOf(chain: string, address: string): string {
  return `${chain}:${address.toLowerCase()}`;
}
