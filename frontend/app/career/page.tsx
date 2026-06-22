"use client";
/* ============================================================
   Career cockpit · /career (CAR-1) — the user's career/personal-brand command
   center, three tabs:
     CV    — the living CV: sections + proof chips, raw export/copy, edit.
     Blog  — blog post manager (draft/published), CRUD metadata.
     Demo  — live-demo / flagship showcase, CRUD.
   Dark command-center aesthetic (shared tokens). All writes fail-closed
   (refetch-after-write; a failed mutation surfaces an error, never silent).
   States: loading · error · empty · data.
   #138-P2 — each tab is a co-located sub-component (_CvTab/_BlogTab/_DemoTab);
   this file is the shell (CareerPage + tab switch). Pure split, no logic change.
   ============================================================ */
import { useState } from "react";
import { useCareer } from "@/lib/useCareer";
import { Icon } from "@/lib/icons";
import { apiBase } from "@/lib/api";
import { CvTab } from "./_CvTab";
import { BlogTab } from "./_BlogTab";
import { DemoTab } from "./_DemoTab";

type Tab = "cv" | "blog" | "demo";

export default function CareerPage() {
  const career = useCareer();
  const { status, errMsg, warning, reload } = career;
  const [tab, setTab] = useState<Tab>("cv");

  return (
    <section className="view" data-screen="CAR" data-testid="career-screen">
      <div className="vtitle">
        <h1>Sự nghiệp & Thương hiệu</h1>
        <span className="sub">CV sống · Blog · Demo showcase</span>
        <span className="sp" />
      </div>

      <div className="row" style={{ gap: 6, flexWrap: "wrap", marginBottom: 6 }} data-testid="career-tabs">
        <button type="button" className={`tab${tab === "cv" ? " on" : ""}`} onClick={() => setTab("cv")} data-testid="tab-cv">
          <Icon name="i-doc" /> CV
        </button>
        <button type="button" className={`tab${tab === "blog" ? " on" : ""}`} onClick={() => setTab("blog")} data-testid="tab-blog">
          <Icon name="i-note" /> Blog
        </button>
        <button type="button" className={`tab${tab === "demo" ? " on" : ""}`} onClick={() => setTab("demo")} data-testid="tab-demo">
          <Icon name="i-bolt" /> Demo
        </button>
      </div>

      {warning && (
        <div className="panel" style={{ padding: "10px 14px" }} data-testid="career-warning">
          <span className="hint mid">⚠ {warning}</span>
        </div>
      )}

      {status === "loading" && (
        <div className="hint" style={{ padding: "24px 4px" }} data-testid="career-loading">Đang tải…</div>
      )}
      {status === "error" && (
        <div className="hint neg" style={{ padding: "24px 4px" }} data-testid="career-error">
          Không tải được dữ liệu sự nghiệp: {errMsg}. Kiểm tra backend ({apiBase}).
          <button className="btn" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
        </div>
      )}

      {status === "ready" && tab === "cv" && <CvTab career={career} />}
      {status === "ready" && tab === "blog" && <BlogTab career={career} />}
      {status === "ready" && tab === "demo" && <DemoTab career={career} />}
    </section>
  );
}
