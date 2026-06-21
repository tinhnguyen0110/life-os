"use client";
/* ============================================================
   /repo-memory (#64-P3 · REPOMEM) — the human browse layer over the per-repo
   knowledge pair: code_insight (a fresh-NOW git read) + repo_memory (the durable
   curated Repos/<name> note an agent writes as it learns a repo).

   Completes #64 [BE + MCP + FE]: P1/P2 are the agent surface (cold-agent reads the
   repo over MCP); this is the human-viewable layer. RENDER-ONLY — the backend
   computes both reads; the FE displays them, honestly:
   - code_insight found:false → "repo not found / not readable" (a warning names why).
   - repo_memory found:false → the honest "no memory note yet" empty-state that
     EXPLAINS the feature (an agent writes it over time) — never a blank panel.

   No mock (net-new). Built from the FROZEN #64 schema + the house panel/empty-state
   style. The repo PICKER lists the tracked projects (GET /projects, render-only); the
   BE resolves name|path. Two reads settle INDEPENDENTLY (one slow/failing panel never
   blocks the other).
   ============================================================ */
import { useEffect, useState } from "react";
import { useRepoMemory } from "@/lib/useRepoMemory";
import { getProjects, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";

export default function RepoMemoryPage() {
  const {
    repo, select, reload,
    insight, insightStatus, insightErr,
    memory, memoryStatus, memoryErr,
  } = useRepoMemory(null);

  // Repo picker options — the tracked projects (render-only; BE resolves name|path).
  const [repos, setRepos] = useState<string[]>([]);
  const [reposErr, setReposErr] = useState("");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await getProjects();
        if (!alive) return;
        const names = (res.data?.projects ?? []).map((p) => p.name).filter(Boolean);
        setRepos(names);
        // auto-select the first repo so the screen shows real data on first paint.
        if (names.length > 0 && repo == null) select(names[0]);
      } catch (e) {
        if (!alive) return;
        setReposErr(e instanceof ApiError ? e.message : (e as Error).message);
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="view" data-screen="REPOMEM" data-testid="repo-memory-screen">
      <div className="vtitle">
        <h1>Repo Memory</h1>
        <span className="sub">
          mỗi repo: đọc cấu trúc tức thời + ghi nhớ bền vững · agent học, người xem
        </span>
        <span className="sp" />
        {repo && (
          <button className="btn" type="button" onClick={reload} data-testid="repo-reload">
            ↻ Tải lại
          </button>
        )}
      </div>

      {/* repo picker */}
      {reposErr && (
        <div className="hint neg" data-testid="repos-error">⚠ Không tải được danh sách repo: {reposErr}</div>
      )}
      <div className="seg" data-testid="repo-picker" role="group" aria-label="Chọn repo">
        {repos.map((r) => (
          <button
            key={r}
            type="button"
            className={repo === r ? "on" : ""}
            aria-pressed={repo === r}
            onClick={() => select(r)}
            data-testid={`repo-opt-${r}`}
          >
            {r}
          </button>
        ))}
      </div>

      {repo == null && repos.length === 0 && !reposErr && (
        <div className="panel" style={{ padding: "20px" }} data-testid="repo-none">
          <div className="hint faint">Chưa có repo nào được theo dõi.</div>
        </div>
      )}

      {repo != null && (
        <div className="grid" style={{ gridTemplateColumns: "1.2fr 1fr", gap: 14, alignItems: "start" }}>
          {/* ── code_insight panel ───────────────────────────────────────────── */}
          <div className="panel" data-testid="insight-panel">
            <div className="phead">
              <span className="kicker">Code Insight · đọc tức thời</span>
              {insight?.asOf && insightStatus === "ready" && insight.found && (
                <span className="hint faint" style={{ marginLeft: "auto" }} data-testid="insight-asof">
                  đọc {relativeTime(insight.asOf)}
                </span>
              )}
            </div>

            {insightStatus === "loading" && (
              <div className="hint faint" style={{ padding: "16px 4px" }} data-testid="insight-loading">
                Đang đọc {repo}…
              </div>
            )}

            {insightStatus === "error" && (
              <div className="hint neg" style={{ padding: "16px 4px" }} data-testid="insight-error">
                Không đọc được repo: {insightErr}.
                <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
              </div>
            )}

            {insightStatus === "ready" && insight && !insight.found && (
              <div className="hint faint" style={{ padding: "16px 4px" }} data-testid="insight-notfound">
                <div style={{ fontWeight: 600, color: "var(--tx-1)" }}>Không tìm thấy repo “{insight.repo}”.</div>
                {insight.warnings.map((w, i) => (
                  <div className="hint mid" key={i} style={{ marginTop: 4 }} data-testid={`insight-warn-${i}`}>⚠ {w}</div>
                ))}
              </div>
            )}

            {insightStatus === "ready" && insight && insight.found && (
              <div data-testid="insight-body" style={{ padding: "4px 2px" }}>
                <div className="hint faint" style={{ fontFamily: "var(--mono)", fontSize: 11, marginBottom: 8 }} data-testid="insight-root">
                  {insight.root}
                </div>

                {/* stack chips */}
                {insight.stack.length > 0 && (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }} data-testid="insight-stack">
                    {insight.stack.map((s) => (
                      <span key={s} className="tagchip" data-testid={`stack-${s}`}>{s}</span>
                    ))}
                  </div>
                )}

                {/* README excerpt (or honest "none") */}
                <div className="kicker" style={{ marginBottom: 4 }}>README</div>
                {insight.readme ? (
                  <pre className="repo-readme" data-testid="insight-readme">{insight.readme}</pre>
                ) : (
                  <div className="hint faint" data-testid="insight-noreadme">Không có README đọc được.</div>
                )}

                {/* structure */}
                <div className="kicker" style={{ margin: "12px 0 4px" }}>Cấu trúc ({insight.structure.length})</div>
                <ul className="repo-tree" data-testid="insight-structure">
                  {insight.structure.map((entry) => (
                    <li key={entry} className={entry.endsWith("/") ? "is-dir" : ""}>{entry}</li>
                  ))}
                </ul>

                {/* recent commits */}
                <div className="kicker" style={{ margin: "12px 0 4px" }}>Commit gần đây ({insight.recentCommits.length})</div>
                {insight.recentCommits.length > 0 ? (
                  <ul className="repo-commits" data-testid="insight-commits">
                    {insight.recentCommits.map((c) => (
                      <li key={c.sha} data-testid={`commit-${c.sha}`}>
                        <span className="repo-sha">{c.sha}</span>
                        <span className="repo-cmsg">{c.msg}</span>
                        <span className="repo-cdate hint faint">{c.date}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="hint faint" data-testid="insight-nocommits">Chưa có commit nào trong tầm đọc.</div>
                )}
              </div>
            )}
          </div>

          {/* ── repo_memory panel ────────────────────────────────────────────── */}
          <div className="panel" data-testid="memory-panel">
            <div className="phead">
              <span className="kicker">Repo Memory · ghi nhớ bền vững</span>
              {memory?.note && memoryStatus === "ready" && (
                <span className="hint faint" style={{ marginLeft: "auto" }} data-testid="memory-updated">
                  cập nhật {relativeTime(memory.note.updated)}
                </span>
              )}
            </div>

            {memoryStatus === "loading" && (
              <div className="hint faint" style={{ padding: "16px 4px" }} data-testid="memory-loading">
                Đang tải ghi nhớ…
              </div>
            )}

            {memoryStatus === "error" && (
              <div className="hint neg" style={{ padding: "16px 4px" }} data-testid="memory-error">
                Không tải được ghi nhớ: {memoryErr}.
                <button className="btn sm" type="button" style={{ marginLeft: 10 }} onClick={reload}>Thử lại</button>
              </div>
            )}

            {/* honest empty-state: no note yet — explain the feature, don't blank. */}
            {memoryStatus === "ready" && memory && (!memory.found || !memory.note) && (
              <div className="repo-mem-empty" style={{ padding: "16px 4px" }} data-testid="memory-empty">
                <div style={{ fontWeight: 600, color: "var(--tx-1)", marginBottom: 6 }}>
                  Chưa có ghi nhớ cho repo này.
                </div>
                <div className="hint faint" style={{ lineHeight: 1.5 }}>
                  Một agent sẽ viết note <span className="acc" style={{ fontFamily: "var(--mono)" }}>Repos/{repo}</span> dần
                  khi nó tìm hiểu repo — kiến trúc, quyết định, điểm cần lưu ý. Khi có, nội dung sẽ hiện ở đây.
                </div>
              </div>
            )}

            {memoryStatus === "ready" && memory?.found && memory.note && (
              <div data-testid="memory-body" style={{ padding: "4px 2px" }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }} data-testid="memory-title">{memory.note.title}</div>
                <pre className="repo-mem-note" data-testid="memory-note-body">{memory.note.body}</pre>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
