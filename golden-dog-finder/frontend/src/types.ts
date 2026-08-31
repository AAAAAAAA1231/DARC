export type TxWindow = {
  buys: number;
  sells: number;
  buyers: number;
  sellers: number;
};

export type PumpState = {
  complete: boolean;
  real_sol: number;
  reply_count: number;
  livestream: boolean;
  nsfw: boolean;
  bonding_curve: string | null;
  creator: string | null;
  ath_mc: number;
};

export type SecurityState = {
  rugged: boolean;
  score: number | null;
  score_normalised: number | null;
  mint_authority: string | null;
  freeze_authority: string | null;
  lp_locked_pct: number | null;
  holders: number | null;
  top_holder_pct: number | null;
  insider_networks: number | null;
  risks: string[];
};

export type Token = {
  chain: string;
  address: string;
  symbol: string;
  name: string;
  dex: string;
  source: string;
  pair_address: string | null;
  price_usd: number;
  market_cap_usd: number;
  fdv_usd: number;
  liquidity_usd: number | null;
  created_at_ms: number;
  volume_m5: number;
  volume_h1: number;
  volume_h6: number;
  volume_h24: number;
  change_m5: number;
  change_h1: number;
  change_h6: number;
  change_h24: number;
  tx_m5: TxWindow;
  tx_m15: TxWindow;
  tx_h1: TxWindow;
  image: string | null;
  websites: string[];
  socials: { type: string; url: string }[];
  boost_amount: number;
  has_profile: boolean;
  pump: PumpState | null;
  security: SecurityState | null;
  url: string | null;
};

export type Gene = {
  id: string;
  name: string;
  score: number;
  max: number;
  reason: string;
};

export type ScoreCard = {
  total: number;
  grade: string;
  passed: boolean;
  kill_reasons: string[];
  genes: Gene[];
  x100_target_mc: number;
  x_if_1m5: number;
  x_if_5m: number;
  x_if_20m: number;
  feasibility: number;
  band: string;
  verdict: string;
  thesis: string;
};

export type Ranked = {
  token: Token;
  score: ScoreCard;
  age_min: number;
};

export type Thesis = {
  title: string;
  promise: string;
  disclaimer: string;
  gates: string[];
  genes: { id: string; name: string; why: string }[];
  targets: { conservative: number; runner: number; stretch: number };
};

export type ScanResponse = {
  scanned_at: number;
  elapsed_ms: number;
  universe: number;
  considered: number;
  passed: number;
  top_score: number;
  top_grade: string;
  errors: string[];
  thesis: Thesis;
  tokens: Ranked[];
};
