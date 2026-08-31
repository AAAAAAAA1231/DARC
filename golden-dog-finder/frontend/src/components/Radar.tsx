import { useMemo } from "react";
import type { Ranked } from "./types";

type Props = {
  tokens: Ranked[];
  selectedKey: string | null;
  onPick: (key: string) => void;
};

export default function Radar({ tokens, selectedKey, onPick }: Props) {
  const blips = useMemo(() => {
    return tokens.slice(0, 18).map((row, i) => {
      const angle = (i / Math.max(tokens.slice(0, 18).length, 1)) * Math.PI * 2 - Math.PI / 2;
      const radius = 18 + (1 - row.score.total / 100) * 34 + (i % 3) * 3;
      return {
        key: `${row.token.chain}:${row.token.address.toLowerCase()}`,
        x: 50 + Math.cos(angle) * radius,
        y: 50 + Math.sin(angle) * radius,
        grade: row.score.grade,
        passed: row.score.passed,
        symbol: row.token.symbol,
      };
    });
  }, [tokens]);

  return (
    <div className="radar-wrap">
      <div className="radar-disc">
        <div className="radar-ring r1" />
        <div className="radar-ring r2" />
        <div className="radar-ring r3" />
        <div className="radar-ring r4" />
        <div className="radar-sweep" />
        <div className="radar-cross" />
        {blips.map((b) => (
          <button
            key={b.key}
            className={`blip grade-${b.grade} ${b.key === selectedKey ? "on" : ""} ${b.passed ? "" : "dead"}`}
            style={{ left: `${b.x}%`, top: `${b.y}%` }}
            onClick={() => onPick(b.key)}
            title={b.symbol}
          />
        ))}
        <div className="radar-core">100x</div>
      </div>
      <p className="radar-caption">越靠近圆心 = 基因分越高。亮点为通过百倍门禁的活标的。</p>
    </div>
  );
}
