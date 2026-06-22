/** Which surface a CV proof chip points at. */
export type ProofKind = "case-study" | "blog" | "demo" | "repo" | "url";
/** A clickable evidence chip on a CV section. */
export interface ProofLink {
  kind: ProofKind;
  label: string;
  /** id (blog/demo) or url. */
  ref: string;
}
/** One parsed H2 section of the living CV (body = raw markdown). */
export interface CvSection {
  id: string;
  heading: string;
  level: number;
  body: string;
  proof: ProofLink[];
}
/** CV header block (name / title / contact line). */
export interface CvMeta {
  name: string;
  title: string;
  contact: string;
}
/** The full living CV. */
export interface Cv {
  meta: CvMeta;
  sections: CvSection[];
  updatedAt: string | null;
  /** True if still the seeded source CV (vs user-edited). */
  seeded: boolean;
}
export type BlogStatus = "draft" | "published";
/** A blog post's metadata (dek = the short description / notes, not full article). */
export interface BlogPost {
  id: string;
  title: string;
  subtitle: string;
  dek: string;
  status: BlogStatus;
  url: string | null;
  tags: string[];
  publishedDate: string | null;
  readMinutes: number | null;
  wordCount: number | null;
  createdAt: string;
  updatedAt: string;
}
/** POST/PUT body for a blog post (id + timestamps server-set). */
export interface BlogInput {
  title: string;
  subtitle?: string;
  dek?: string;
  status?: BlogStatus;
  url?: string | null;
  tags?: string[];
  publishedDate?: string | null;
  readMinutes?: number | null;
  wordCount?: number | null;
}
export type DemoStatus = "live" | "wip" | "offline";
/** A live demo / flagship project in the showcase. */
export interface DemoItem {
  id: string;
  name: string;
  tagline: string;
  desc: string;
  url: string | null;
  repo: string | null;
  status: DemoStatus;
  tags: string[];
  loc: number | null;
  createdAt: string;
  updatedAt: string;
}
/** POST/PUT body for a demo item (id + timestamps server-set). */
export interface DemoInput {
  name: string;
  tagline?: string;
  desc?: string;
  url?: string | null;
  repo?: string | null;
  status?: DemoStatus;
  tags?: string[];
  loc?: number | null;
}

/* ============================================================
   Decision tower (FINANCE-ASSISTANT P1–P4) — MIRRORS the LIVE /decision/* payloads
   (curled on :8686). The tower is NEUTRAL by backend design: it surfaces DATA + the
   guardian's QUESTIONS, never advice. SELF-DESCRIBING RAW: every q/W/delta is
   backend-computed (W = ∏ layer-q, pure product, NO clamp) — the FE renders + formats
   + colors, NEVER recomputes. Two distinct numbers (§116): `weight` = signal strength
   (∏ of layer q); `confidence` = trust in the measurement — render them as DISTINCT
   visuals, never one conflated "score".
   ============================================================ */
