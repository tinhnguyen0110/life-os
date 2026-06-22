import { apiGet, apiPost, apiPut, apiPatch } from "./_client";
import type {
  ApiResponse,
  ChannelDetail,
  CryptoBasis,
  ExchangeOverview,
  FinanceOverview,
  Holding,
  HoldingInput,
} from "@/lib/types";

/** S5 — finance overview (totalValue + allocations + dryPowder + pnlTotal). */
export function getFinance(): Promise<ApiResponse<FinanceOverview>> {
  return apiGet<FinanceOverview>("/finance");
}
/** S6 — add a holding (POST /finance/holdings). Bad field → ApiError(422) per-field.
 *  Returns the created Holding (the caller refetches GET /finance for the new overview). */
export function createHolding(body: HoldingInput): Promise<ApiResponse<Holding>> {
  return apiPost<Holding>("/finance/holdings", body);
}
/** S6 — one channel's detail (alloc + priced holdings + ladder). 404 if unknown. */
export function getChannelDetail(channel: string): Promise<ApiResponse<ChannelDetail>> {
  return apiGet<ChannelDetail>(`/finance/${encodeURIComponent(channel)}`);
}
/** OKX exchange overview (balances + positions). configured=false if no API key. */
export function getExchange(): Promise<ApiResponse<ExchangeOverview>> {
  return apiGet<ExchangeOverview>("/exchange");
}
/** Force a fresh pull from OKX (bypasses in-memory cache). */
export function syncExchange(): Promise<ApiResponse<ExchangeOverview>> {
  return apiPatch<ExchangeOverview>("/exchange/sync");
}
/** Finance — get crypto cost basis (snapshot or manual override). */
export function getCryptoBasis(): Promise<ApiResponse<CryptoBasis>> {
  return apiGet<CryptoBasis>("/finance/crypto-basis");
}
/** #74 change 5 — verify the privacy reveal-pass. The pass lives in BE env (never sent
 *  to the FE); we POST the user's ATTEMPT and read data.ok. Always HTTP 200 (a wrong
 *  pass is data.ok=false, not an error). */
export function verifyPrivacyPass(pass: string): Promise<ApiResponse<{ ok: boolean }>> {
  return apiPost<{ ok: boolean }>("/settings/privacy/verify", { pass });
}
/** Finance — user override for crypto cost basis (PUT /finance/crypto-basis). */
export function setCryptoBasis(basis: number): Promise<ApiResponse<CryptoBasis>> {
  return apiPut<CryptoBasis>("/finance/crypto-basis", { basis });
}

/* ---- Wiki (W1–W5 · integer-ID PKM) — frozen M1 contract (end_sprint_W1c §3) ---- */
