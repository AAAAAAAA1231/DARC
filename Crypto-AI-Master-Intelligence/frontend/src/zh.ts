/** UI labels. Status tokens stay English on the wire; this is display-only. */

export const STATUS_ZH: Record<string, string> = {
  UNKNOWN: "未知",
  OK: "正常",
  SAFE: "安全",
  LOW_RISK: "低风险",
  HIGH_RISK: "高风险",
  MALICIOUS: "恶意",
  ERROR: "错误",
  BULL: "偏多",
  BEAR: "偏空",
  LONG: "做多",
  SHORT: "做空",
  HOLD: "观望",
  NATIVE_PROTOCOL: "原生协议",
  MISSING_KEY: "缺少密钥",
  DOWN: "不可用",
  TIMEOUT: "超时",
};

export function statusZh(value?: string | null): string {
  if (value == null || value === "") return "未知";
  const key = String(value).toUpperCase();
  return STATUS_ZH[key] || value;
}
