/* ============================================================
   Notes (S10) — MIRRORS backend modules/notes/schema.py EXACTLY (Sprint 6, FROZEN).
   NOTE: `attach` is a NESTED {type, ref} object (NOT flat attachedType/attachedId).
   ref required when type != "none". List returns pinned-first → updatedAt-desc.
   ============================================================ */
export type AttachType = "project" | "channel" | "none";
export interface Attach {
  type: AttachType;
  /** project id / channel id / null. Required when type != "none". */
  ref?: string | null;
}
/** A stored note — mirrors `Note`. id = slug(title)-6hex; timestamps ISO UTC. */
export interface Note {
  id: string;
  title: string;
  body: string;
  tags: string[];
  pinned: boolean;
  attach: Attach;
  createdAt: string;
  updatedAt: string;
}
/** POST/PUT body — mirrors `NoteInput`. id/timestamps server-assigned; title required. */
export interface NoteInput {
  title: string;
  body?: string;
  tags?: string[];
  pinned?: boolean;
  attach?: Attach;
}
