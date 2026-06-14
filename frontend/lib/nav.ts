/* ============================================================
   Nav config — D3 (plan_sprint_0.md): 6 groups, 14 screens S1–S14.
   SPEC §1 grouping: Tổng quan / Dự án / Tài chính / Hằng ngày / Hệ thống(Tự động) / Cấu hình.
   DEVIATION from mock NAV (ARCH §11): mock "AI Brain" item DROPPED — no embedded AI.
   Badges: nav.ts values are the FAIL-SOFT FALLBACK; Sidebar.tsx wires the live
   values (routines/projects/market/claude-usage) — F2-M4.
   `route` = Next.js App Router path; "/" = S1 Home (app/page.tsx).
   ============================================================ */
import type { IconKey } from "./icons";

export type BadgeClass = "r" | "a" | "g" | "acc";

export interface NavItem {
  /** App Router path. */
  route: string;
  /** Breadcrumb / sidebar label. */
  label: string;
  icon: IconKey;
  /** Screen id (S1–S14) for reference. */
  screen: string;
  badge?: { text: string; cls: BadgeClass };
}

export interface NavGroup {
  sec: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    sec: "Tổng quan",
    items: [{ route: "/", label: "Home", icon: "i-home", screen: "S1" }],
  },
  {
    sec: "Dự án",
    items: [
      { route: "/projects", label: "Danh sách", icon: "i-proj", screen: "S2", badge: { text: "4", cls: "acc" } },
      { route: "/graveyard", label: "Nghĩa địa", icon: "i-grave", screen: "S4" },
    ],
  },
  {
    sec: "Tài chính",
    items: [
      { route: "/finance", label: "Tổng quan tài chính", icon: "i-fin", screen: "S5" },
      { route: "/portfolio", label: "Danh mục", icon: "i-pie", screen: "S6" },
      { route: "/exchange", label: "OKX Exchange", icon: "i-mkt", screen: "S-okx" },
      { route: "/journal", label: "Nhật ký lệnh", icon: "i-journal", screen: "S7" },
      { route: "/market", label: "Thị trường", icon: "i-mkt", screen: "S8", badge: { text: "2", cls: "r" } },
    ],
  },
  {
    sec: "Hằng ngày",
    items: [
      { route: "/claude-usage", label: "Claude Usage", icon: "i-cpu", screen: "S9", badge: { text: "71%", cls: "r" } },
      { route: "/notes", label: "Ghi chú", icon: "i-note", screen: "S10" },
      { route: "/decision-journal", label: "Quyết định", icon: "i-journal", screen: "DJ" },
    ],
  },
  {
    sec: "Tri thức",
    items: [
      // W1 Vault · W3 Inbox · W4 Graph · P1 Proposals · W5 MOC · A1c Sync —
      // all live + linked (each resolves to a real screen). No inbox badge.
      { route: "/wiki", label: "Wiki Home", icon: "i-home", screen: "W1" },
      { route: "/wiki/inbox", label: "Wiki Inbox", icon: "i-note", screen: "W3" },
      { route: "/wiki/graph", label: "Graph", icon: "i-graph", screen: "W4" },
      { route: "/wiki/proposals", label: "Proposals", icon: "i-pin", screen: "P1" },
      { route: "/wiki/moc", label: "MOC", icon: "i-moc", screen: "W5" },
      { route: "/wiki/sync", label: "Sync & Integrity", icon: "i-merge", screen: "A1c" },
    ],
  },
  {
    sec: "Hệ thống",
    items: [
      { route: "/routines", label: "Automation", icon: "i-bolt", screen: "S13", badge: { text: "5", cls: "g" } },
      { route: "/activity", label: "Activity Feed", icon: "i-pulse", screen: "S14" },
    ],
  },
  {
    sec: "Cấu hình",
    items: [
      { route: "/brief", label: "Brief", icon: "i-doc", screen: "S11" },
      { route: "/settings", label: "Cài đặt", icon: "i-set", screen: "S12" },
    ],
  },
];

/** Flat lookup: route → label (breadcrumb) + screen. Includes detail sub-routes. */
export const CRUMB: Record<string, string> = {
  "/": "Home",
  "/projects": "Dự án",
  "/graveyard": "Nghĩa địa dự án",
  "/finance": "Tài chính",
  "/portfolio": "Danh mục",
  "/journal": "Nhật ký lệnh",
  "/market": "Thị trường & Cảnh báo",
  "/exchange": "OKX Exchange",
  "/claude-usage": "Claude Usage",
  "/notes": "Ghi chú",
  "/decision-journal": "Nhật ký quyết định",
  "/brief": "Brief hôm nay",
  "/settings": "Cài đặt",
  "/routines": "Automation / Routines",
  "/activity": "Activity Feed",
  // Wiki (W1–W5) — detail route /wiki/[id] resolves to the parent crumb (TopBar
  // crumbFor falls back to the first path segment). Full "Tri thức" NAV group = T3.
  "/wiki": "Vault · Tri thức",
  "/wiki/inbox": "Inbox / Refine",
  "/wiki/graph": "Graph Explorer",
  "/wiki/proposals": "Proposal Queue",
  "/wiki/moc": "MOC · Synthesize",
  "/wiki/sync": "Sync & Integrity",
};

/** All 14 screen routes (detail routes resolve under their parent nav item). */
export const ALL_ROUTES = NAV.flatMap((g) => g.items.map((i) => i.route));
