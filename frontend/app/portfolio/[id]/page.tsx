"use client";
/* ============================================================
   S6 — Portfolio / channel detail. Route [id] = channel (e.g. crypto).
   GET /finance/{channel} → { alloc, holdings[priced], ladder }.
   SELF-DESCRIBING RAW: drift/pnl/ladder-distance are backend-computed — FE renders
   + formats + colors, NEVER recomputes. null → "—". 404 → not-found state.
   Sections: position summary (alloc+drift+pnl) · ladder state (rung/trigger/
   distance) · priced holdings table · journal link.
   ============================================================ */
import { useEffect, useState } from "react";
import { useSafeRouter } from "@/lib/useNav";
import { getChannelDetail, apiBase, ApiError } from "@/lib/api";
import type { ChannelDetail, PricedHolding } from "@/lib/types";
import { KpiCard } from "@/components/shared/KpiCard";
import { LoadErrorShell } from "@/components/LoadErrorShell";
import { DataTable, type Column } from "@/components/shared/DataTable";
import { fmtUSD, fmtSign, fmtPct } from "@/lib/format";
import { Icon } from "@/lib/icons";

function pnlCls(abs: number | null | undefined): string {
  if (abs == null || !Number.isFinite(abs) || abs === 0) return "faint";
  return abs < 0 ? "neg" : "pos";
}

export default function PortfolioDetailPage({ params }: { params?: { id?: string } }) {
  const channel = params?.id ?? "";
  const router = useSafeRouter();
  const [detail, setDetail] = useState<ChannelDetail | null>(null);
  const [status, setStatus] = useState<"loading" | "notfound" | "error" | "ready">("loading");
  const [errMsg, setErrMsg] = useState("");

  async function load() {
    setStatus("loading");
    try {
      const res = await getChannelDetail(channel);
      setDetail(res.data);
      setStatus("ready");
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setStatus("notfound");
      else {
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    }
  }

  useEffect(() => {
    if (!channel) {
      setStatus("notfound");
      return;
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channel]);

  // #138-P1a-rollout — loading + error use the shared <LoadErrorShell> (verbatim copy/testid/
  // wrapper). The `notfound` branch below is a custom empty-state → left as-is (not the shell).
  if (status === "loading") {
    return (
      <LoadErrorShell
        status="loading"
        sectionClassName="view"
        dataScreen="S6"
        loadingTestid="pf-loading"
        loadingLabel="Đang tải vị thế…"
        errorLabel={null}
      >
        {null}
      </LoadErrorShell>
    );
  }

  if (status === "notfound") {
    return (
      <section className="view" data-screen="S6">
        <div className="empty-screen" data-testid="pf-notfound">
          <div className="es-icon"><Icon name="i-pie" /></div>
          <h1>Không tìm thấy kênh</h1>
          <span className="es-meta">Kênh “{channel}” không có trong danh mục.</span>
          <button className="btn" type="button" onClick={() => router.push("/finance")}>← Về tài chính</button>
        </div>
      </section>
    );
  }

  if (status === "error" || !detail) {
    return (
      <LoadErrorShell
        status="error"
        sectionClassName="view"
        dataScreen="S6"
        errorTestid="pf-error"
        errorLabel={<>Lỗi tải vị thế: {errMsg}. Kiểm tra backend ({apiBase}).</>}
        reload={load}
        loadingLabel={null}
      >
        {null}
      </LoadErrorShell>
    );
  }

  const { alloc, holdings, ladder } = detail;
  const driftAlert = alloc.driftAlert ?? Math.abs(alloc.drift) > 5;

  const holdingColumns: Column<PricedHolding>[] = [
    { key: "symbol", header: "Mã", className: "pn", cell: (h) => h.holding.symbol },
    { key: "qty", header: "Số lượng", cell: (h) => h.holding.qty },
    { key: "avgCost", header: "Giá vốn", className: "faint", cell: (h) => fmtUSD(h.holding.avgCost) },
    { key: "price", header: "Giá hiện tại", className: "mut", cell: (h) => fmtUSD(h.price) },
    { key: "value", header: "Giá trị", className: "num", cell: (h) => fmtUSD(h.value) },
    {
      key: "pnl",
      header: "P&L",
      cell: (h) => <span className={pnlCls(h.pnl?.abs)}>{h.pnl ? `${fmtSign(h.pnl.abs)} (${fmtPct(h.pnl.pct)})` : "—"}</span>,
    },
    { key: "src", header: "Nguồn", className: "faint", cell: (h) => h.source },
  ];

  return (
    <section className="view" data-screen="S6" data-testid="pf-screen">
      <div className="detail-head" style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button className="btn" type="button" onClick={() => router.push("/finance")} aria-label="Quay lại" data-testid="pf-back">←</button>
        <h1 style={{ textTransform: "capitalize" }}>{alloc.channel}</h1>
        <span className="sub">{holdings.length} vị thế</span>
        <span className="sp" />
        <button className="btn" type="button" onClick={() => router.push("/journal")}>
          <Icon name="i-journal" /> Nhật ký
        </button>
      </div>

      {/* Position summary — alloc + drift (render-only) + pnl */}
      <div className="grid g-4">
        <KpiCard label="Giá trị kênh" value={fmtUSD(alloc.value)} />
        <KpiCard
          label="Phân bổ"
          value={`${alloc.pct.toFixed(0)}%`}
          tone={driftAlert ? "mid" : "default"}
          sub={`mục tiêu ${alloc.target.toFixed(0)}% · lệch ${alloc.drift >= 0 ? "+" : "−"}${Math.abs(alloc.drift).toFixed(1)}${driftAlert ? " ⚠" : ""}`}
        />
        <KpiCard label="P&L kênh" value={fmtSign(alloc.pnl.abs)} tone={alloc.pnl.abs < 0 ? "neg" : "pos"} sub={fmtPct(alloc.pnl.pct)} />
        <KpiCard label="Vốn" value={fmtUSD(alloc.pnl.cost)} sub="cost basis" />
      </div>

      {/* Ladder state */}
      <div className="panel" data-testid="pf-ladder">
        <div className="phead">
          <span className="kicker">Ladder DCA</span>
          {ladder && <span className="hint" style={{ marginLeft: "auto" }}>{ladder.rungsIn} rung đã vào</span>}
        </div>
        <div style={{ padding: "10px 16px 14px" }}>
          {ladder ? (
            <div className="row" style={{ flexWrap: "wrap", gap: 18, fontFamily: "var(--mono)", fontSize: 12.5 }}>
              <span><span className="faint">Tham chiếu</span> <b>{fmtUSD(ladder.referencePrice)}</b></span>
              <span><span className="faint">Hiện tại</span> <b className="num">{fmtUSD(ladder.currentPrice)}</b></span>
              {ladder.nextRung ? (
                <span data-testid="pf-nextrung">
                  <span className="faint">Rung kế</span> <b className="acc">{fmtUSD(ladder.nextRung.triggerPrice)}</b>
                  {" "}({ladder.nextRung.pct}%)
                  {ladder.distancePct != null && <span className="faint"> · còn cách {Math.abs(ladder.distancePct).toFixed(1)}%</span>}
                </span>
              ) : (
                <span className="pos">Đã vào tất cả rung ✓</span>
              )}
            </div>
          ) : (
            <span className="hint">Chưa cấu hình ladder cho kênh này.</span>
          )}
        </div>
      </div>

      {/* Priced holdings */}
      <div className="panel" style={{ overflow: "hidden" }}>
        <div className="phead"><span className="kicker">Vị thế</span></div>
        <DataTable
          columns={holdingColumns}
          rows={holdings}
          rowKey={(h, i) => `${h.holding.symbol}-${i}`}
          emptyLabel="Chưa có vị thế nào trong kênh."
        />
      </div>
    </section>
  );
}
