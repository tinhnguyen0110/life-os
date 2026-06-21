import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/* #64-P3 Repo Memory screen — render-only browse of code_insight + repo_memory.
   Mocks the NAMED api fns the component calls (getProjects/getCodeInsight/
   getRepoMemory) — NOT lower-level apiGet (mock-named-api lesson). mockResolvedValue
   (steady-state, not ...Once → refetch/reload won't exhaust → no unhandled rejection
   per unhandled-errors-not-green). Asserts scoped to testids
   (scope-no-fabrication-asserts-to-element). The HARD GATE distinguishing cases:
   code_insight found:true → sections render / found:false → honest "not found";
   repo_memory found:true → note renders / found:false → honest "no note yet". */

const getProjects = vi.fn();
const getCodeInsight = vi.fn();
const getRepoMemory = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getProjects: (...a: unknown[]) => getProjects(...a),
    getCodeInsight: (...a: unknown[]) => getCodeInsight(...a),
    getRepoMemory: (...a: unknown[]) => getRepoMemory(...a),
  };
});

import RepoMemoryPage from "../page";

afterEach(() => {
  getProjects.mockReset();
  getCodeInsight.mockReset();
  getRepoMemory.mockReset();
});

const PROJECTS = (names = ["life-os", "cairn"]) => ({
  success: true,
  data: { projects: names.map((name) => ({ name })), summary: {} },
});

const INSIGHT_FOUND = (over = {}) => ({
  success: true,
  data: {
    repo: "life-os",
    root: "/tinhdev/life-os",
    found: true,
    structure: ["backend/", "frontend/", "README.md", "docker-compose.yml"],
    readme: "# Life OS\n\nPersonal AI operating system.",
    recentCommits: [
      { sha: "abc1234", msg: "feat: ship the thing", date: "2026-06-21" },
      { sha: "def5678", msg: "fix: the other thing", date: "2026-06-20" },
    ],
    stack: ["docker", "python", "nextjs"],
    asOf: "2026-06-21T10:45:42+00:00",
    warnings: [],
    ...over,
  },
});

const INSIGHT_NOTFOUND = (over = {}) => ({
  success: true,
  data: {
    repo: "ghost-repo",
    root: "",
    found: false,
    structure: [],
    readme: null,
    recentCommits: [],
    stack: [],
    asOf: "2026-06-21T10:45:42+00:00",
    warnings: ["repo 'ghost-repo' not found under the configured roots"],
    ...over,
  },
});

const MEMORY_NONE = (repo = "life-os") => ({
  success: true,
  data: { repo, note: null, found: false },
});

const MEMORY_FOUND = (repo = "life-os") => ({
  success: true,
  data: {
    repo,
    found: true,
    note: { id: "n1", title: "Repos/life-os", body: "## Architecture\nModule-per-screen.", updated: "2026-06-21T09:00:00+00:00" },
  },
});

describe("S REPOMEM — Repo Memory browse (#64-P3)", () => {
  it("renders the repo picker from the tracked projects + auto-selects the first", async () => {
    getProjects.mockResolvedValue(PROJECTS(["life-os", "cairn"]));
    getCodeInsight.mockResolvedValue(INSIGHT_FOUND());
    getRepoMemory.mockResolvedValue(MEMORY_NONE());

    render(<RepoMemoryPage />);
    await waitFor(() => expect(screen.getByTestId("repo-picker")).toBeInTheDocument());
    expect(screen.getByTestId("repo-opt-life-os")).toBeInTheDocument();
    expect(screen.getByTestId("repo-opt-cairn")).toBeInTheDocument();
    // auto-selected the first → its option is pressed
    await waitFor(() => expect(screen.getByTestId("repo-opt-life-os").getAttribute("aria-pressed")).toBe("true"));
  });

  // HARD GATE — code_insight found:true → all sections render.
  it("code_insight found:true → structure/README/commits/stack/asOf all render", async () => {
    getProjects.mockResolvedValue(PROJECTS());
    getCodeInsight.mockResolvedValue(INSIGHT_FOUND());
    getRepoMemory.mockResolvedValue(MEMORY_NONE());

    render(<RepoMemoryPage />);
    await waitFor(() => expect(screen.getByTestId("insight-body")).toBeInTheDocument());
    const panel = screen.getByTestId("insight-panel");
    // stack chips
    expect(within(panel).getByTestId("stack-docker")).toBeInTheDocument();
    expect(within(panel).getByTestId("stack-python")).toBeInTheDocument();
    // README excerpt
    expect(within(panel).getByTestId("insight-readme")).toHaveTextContent("Personal AI operating system");
    // structure
    expect(within(panel).getByTestId("insight-structure")).toHaveTextContent("frontend/");
    // commits (sha + msg + date)
    expect(within(panel).getByTestId("commit-abc1234")).toHaveTextContent("feat: ship the thing");
    expect(within(panel).getByTestId("commit-abc1234")).toHaveTextContent("2026-06-21");
    // asOf freshness stamp present
    expect(within(panel).getByTestId("insight-asof")).toBeInTheDocument();
  });

  // HARD GATE — code_insight found:false → honest "not found", NOT blank/crash.
  it("code_insight found:false → honest 'not found' + the warning (no blank/crash)", async () => {
    getProjects.mockResolvedValue(PROJECTS(["ghost-repo"]));
    getCodeInsight.mockResolvedValue(INSIGHT_NOTFOUND());
    getRepoMemory.mockResolvedValue(MEMORY_NONE("ghost-repo"));

    render(<RepoMemoryPage />);
    const nf = await screen.findByTestId("insight-notfound");
    expect(nf).toHaveTextContent("Không tìm thấy repo");
    expect(within(nf).getByTestId("insight-warn-0")).toHaveTextContent("not found under the configured roots");
    // the body (sections) must NOT render
    expect(screen.queryByTestId("insight-body")).toBeNull();
  });

  // README null → honest "no readme", not a blank or "null" string.
  it("code_insight readme=null → 'không có README' (no 'null' literal)", async () => {
    getProjects.mockResolvedValue(PROJECTS());
    getCodeInsight.mockResolvedValue(INSIGHT_FOUND({ ...INSIGHT_FOUND().data, readme: null }));
    getRepoMemory.mockResolvedValue(MEMORY_NONE());

    render(<RepoMemoryPage />);
    await waitFor(() => expect(screen.getByTestId("insight-noreadme")).toBeInTheDocument());
    expect(screen.queryByText(/^null$/)).toBeNull();
    expect(screen.queryByTestId("insight-readme")).toBeNull();
  });

  // HARD GATE — repo_memory found:false → honest empty-state explaining the feature.
  it("repo_memory found:false → honest 'no note yet' empty-state (NOT blank)", async () => {
    getProjects.mockResolvedValue(PROJECTS());
    getCodeInsight.mockResolvedValue(INSIGHT_FOUND());
    getRepoMemory.mockResolvedValue(MEMORY_NONE());

    render(<RepoMemoryPage />);
    const empty = await screen.findByTestId("memory-empty");
    expect(empty).toHaveTextContent("Chưa có ghi nhớ");
    expect(empty).toHaveTextContent("Repos/life-os"); // explains where the agent writes it
    expect(screen.queryByTestId("memory-body")).toBeNull();
  });

  // HARD GATE — repo_memory found:true → the note renders (title + body).
  it("repo_memory found:true → the note title + body render", async () => {
    getProjects.mockResolvedValue(PROJECTS());
    getCodeInsight.mockResolvedValue(INSIGHT_FOUND());
    getRepoMemory.mockResolvedValue(MEMORY_FOUND());

    render(<RepoMemoryPage />);
    const body = await screen.findByTestId("memory-body");
    expect(within(body).getByTestId("memory-title")).toHaveTextContent("Repos/life-os");
    expect(within(body).getByTestId("memory-note-body")).toHaveTextContent("Module-per-screen");
    expect(screen.queryByTestId("memory-empty")).toBeNull();
  });

  // Independent settle — code_insight error must NOT block the memory panel.
  it("code_insight ERROR but repo_memory OK → insight shows error, memory still renders", async () => {
    getProjects.mockResolvedValue(PROJECTS());
    getCodeInsight.mockRejectedValue(new Error("insight 500"));
    getRepoMemory.mockResolvedValue(MEMORY_FOUND());

    render(<RepoMemoryPage />);
    await waitFor(() => expect(screen.getByTestId("insight-error")).toHaveTextContent("insight 500"));
    // memory panel still rendered its note (independent settle)
    expect(screen.getByTestId("memory-body")).toBeInTheDocument();
  });

  // Switching repos re-fetches both with the new repo.
  it("selecting a different repo re-fetches code_insight + repo_memory for it", async () => {
    getProjects.mockResolvedValue(PROJECTS(["life-os", "cairn"]));
    getCodeInsight.mockResolvedValue(INSIGHT_FOUND());
    getRepoMemory.mockResolvedValue(MEMORY_NONE());

    render(<RepoMemoryPage />);
    await waitFor(() => expect(screen.getByTestId("insight-body")).toBeInTheDocument());
    getCodeInsight.mockClear();
    getRepoMemory.mockClear();

    const user = userEvent.setup();
    await user.click(screen.getByTestId("repo-opt-cairn"));
    await waitFor(() => expect(getCodeInsight).toHaveBeenCalledWith("cairn"));
    expect(getRepoMemory).toHaveBeenCalledWith("cairn");
  });

  // projects fetch fails → honest picker error, no crash.
  it("projects fetch fails → honest picker error (no crash)", async () => {
    getProjects.mockRejectedValue(new Error("projects down"));
    render(<RepoMemoryPage />);
    await waitFor(() => expect(screen.getByTestId("repos-error")).toHaveTextContent("projects down"));
  });
});
