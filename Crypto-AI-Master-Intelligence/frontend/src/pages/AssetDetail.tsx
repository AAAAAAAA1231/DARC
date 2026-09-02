import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import CandleChart from "../components/CandleChart";
import HoldingBadge from "../components/HoldingBadge";
import { Button, Panel, Status } from "../components/ui";
import { fmtNum, fmtUsd } from "../format";

export default function AssetDetail() {
  const { symbol = "BTCUSDT" } = useParams();
  const [data, setData] = useState<any>(null);
  const [interval, setInterval] = useState("1d");
  const [busy, setBusy] = useState(false);

  async function load(iv = interval) {
    setBusy(true);
    try {
      setData(await api(`/api/assets/${encodeURIComponent(symbol)}?interval=${iv}&limit=180`));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load(interval);
  }, [symbol]);

  const ticker = data?.ticker || {};
  return (
    <div className="space-y-4">
      <Panel
        title={`${data?.symbol || symbol}`}
        action={
          <div className="flex gap-2">
            {["1h", "4h", "1d"].map((iv) => (
              <Button
                key={iv}
                disabled={busy}
                onClick={() => {
                  setInterval(iv);
                  load(iv);
                }}
              >
                {iv}
              </Button>
            ))}
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-2 text-sm md:grid-cols-4">
          <div>Last {fmtNum(ticker.last ?? ticker.close, 2)}</div>
          <div>24h {ticker.price_change_pct != null ? `${Number(ticker.price_change_pct).toFixed(2)}%` : "UNKNOWN"}</div>
          <div>Volume {ticker.quote_volume != null ? fmtUsd(ticker.quote_volume) : "UNKNOWN"}</div>
          <div>Source <Status value={data?.source_status?.status} /></div>
        </div>
        <HoldingBadge overlay={data?.holding} />
        <div className="mt-3">
          <CandleChart candles={data?.candles} height={360} />
        </div>
      </Panel>
    </div>
  );
}
