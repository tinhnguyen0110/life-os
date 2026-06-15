/**
 * career.test.tsx — CAR-1 Career cockpit (frontend-owned). Mocks the named API
 * wrappers the useCareer hook calls (getCareerCv/getCareerBlog/getCareerDemo +
 * the write fns). Behavior-tested: tab switch renders the right surface, CV
 * sections + proof chips render, blog/demo cards render, and WRITE-FAILURE
 * teeth-tests (a failed POST surfaces an error + keeps the form open, fail-closed).
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const getCareerCv = vi.fn();
const getCareerCvRaw = vi.fn();
const updateCareerCv = vi.fn();
const getCareerBlog = vi.fn();
const createCareerBlog = vi.fn();
const updateCareerBlog = vi.fn();
const deleteCareerBlog = vi.fn();
const getCareerDemo = vi.fn();
const createCareerDemo = vi.fn();
const updateCareerDemo = vi.fn();
const deleteCareerDemo = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getCareerCv: (...a: unknown[]) => getCareerCv(...a),
    getCareerCvRaw: (...a: unknown[]) => getCareerCvRaw(...a),
    updateCareerCv: (...a: unknown[]) => updateCareerCv(...a),
    getCareerBlog: (...a: unknown[]) => getCareerBlog(...a),
    createCareerBlog: (...a: unknown[]) => createCareerBlog(...a),
    updateCareerBlog: (...a: unknown[]) => updateCareerBlog(...a),
    deleteCareerBlog: (...a: unknown[]) => deleteCareerBlog(...a),
    getCareerDemo: (...a: unknown[]) => getCareerDemo(...a),
    createCareerDemo: (...a: unknown[]) => createCareerDemo(...a),
    updateCareerDemo: (...a: unknown[]) => updateCareerDemo(...a),
    deleteCareerDemo: (...a: unknown[]) => deleteCareerDemo(...a),
  };
});

import CareerPage from "../page";
import { ApiError } from "@/lib/api";

const CV = {
  success: true,
  data: {
    meta: { name: "Nguyen Van Tinh", title: "AI Automation Engineer", contact: "✉ x@y.com" },
    sections: [
      { id: "summary", heading: "SUMMARY", level: 2, body: "I build **trustworthy** agents.", proof: [] },
      {
        id: "skills", heading: "SKILLS", level: 2, body: "Python, Go.",
        proof: [{ kind: "blog", label: "Anti-hallucination", ref: "blog-1" }],
      },
    ],
    updatedAt: "2026-06-15T00:00:00Z", seeded: true,
  },
};
const BLOG = (posts: unknown[]) => ({ success: true, data: posts });
const DEMO = (items: unknown[]) => ({ success: true, data: items });
const POST = (over = {}) => ({
  id: "p1", title: "Code-Enforce", subtitle: "Anti-Hall", dek: "prompt reduces, code guarantees",
  status: "published", url: "https://blog.x/p1", tags: ["AI"], publishedDate: "2026-06-14",
  readMinutes: 10, wordCount: 1980, createdAt: "2026-06-14T00:00:00Z", updatedAt: "2026-06-14T00:00:00Z", ...over,
});
const ITEM = (over = {}) => ({
  id: "d1", name: "OutboundOS", tagline: "Agent-first pipeline", desc: "anti-hallucination",
  url: "https://demo.x/o", repo: null, status: "live", tags: ["agentic"], loc: 122000,
  createdAt: "2026-06-01T00:00:00Z", updatedAt: "2026-06-01T00:00:00Z", ...over,
});

function primeReads(posts: unknown[] = [POST()], items: unknown[] = [ITEM()]) {
  getCareerCv.mockResolvedValue(CV);
  getCareerBlog.mockResolvedValue(BLOG(posts));
  getCareerDemo.mockResolvedValue(DEMO(items));
}

afterEach(() => {
  [getCareerCv, getCareerCvRaw, updateCareerCv, getCareerBlog, createCareerBlog, updateCareerBlog,
    deleteCareerBlog, getCareerDemo, createCareerDemo, updateCareerDemo, deleteCareerDemo]
    .forEach((m) => m.mockReset());
});

describe("CAR-1 Career — CV tab", () => {
  it("renders CV meta + sections on first load (cv tab default)", async () => {
    primeReads();
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("cv-tab")).toBeInTheDocument());
    expect(screen.getByTestId("cv-name").textContent).toContain("Nguyen Van Tinh");
    expect(screen.getByTestId("cv-section-summary")).toBeInTheDocument();
    expect(screen.getByTestId("cv-section-skills")).toBeInTheDocument();
  });

  it("renders proof chips on a section that has them", async () => {
    primeReads();
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("cv-proof-skills")).toBeInTheDocument());
    expect(screen.getByText("Anti-hallucination")).toBeInTheDocument();
  });

  it("CV edit save fail surfaces error + keeps editor open (fail-closed)", async () => {
    primeReads();
    getCareerCvRaw.mockResolvedValue({ success: true, data: { markdown: "# Old CV\n## SUMMARY\nx" } });
    updateCareerCv.mockRejectedValue(new ApiError(500, "boom"));
    const user = userEvent.setup();
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("cv-edit")).toBeInTheDocument());
    await user.click(screen.getByTestId("cv-edit"));
    await waitFor(() => expect(screen.getByTestId("cv-editor")).toBeInTheDocument());
    await user.click(screen.getByTestId("cv-save"));
    await waitFor(() => expect(screen.getByTestId("cv-form-error")).toBeInTheDocument());
    // editor stays OPEN (fail-closed — not closed as if saved)
    expect(screen.getByTestId("cv-editor")).toBeInTheDocument();
  });
});

describe("CAR-1 Career — Blog tab", () => {
  it("switches to blog tab and renders post cards", async () => {
    primeReads([POST(), POST({ id: "p2", title: "Self-Improving", status: "draft" })]);
    const user = userEvent.setup();
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("cv-tab")).toBeInTheDocument());
    await user.click(screen.getByTestId("tab-blog"));
    await waitFor(() => expect(screen.getByTestId("blog-tab")).toBeInTheDocument());
    expect(screen.getByText("Code-Enforce")).toBeInTheDocument();
    expect(screen.getByText("Self-Improving")).toBeInTheDocument();
    expect(screen.getByTestId("blog-status-p2").textContent).toContain("draft");
  });

  it("create-post failure surfaces error + keeps form open (fail-closed)", async () => {
    primeReads([]);
    createCareerBlog.mockRejectedValue(new ApiError(422, "title required"));
    const user = userEvent.setup();
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("cv-tab")).toBeInTheDocument());
    await user.click(screen.getByTestId("tab-blog"));
    await user.click(screen.getByTestId("blog-new"));
    await waitFor(() => expect(screen.getByTestId("blog-form")).toBeInTheDocument());
    await user.type(screen.getByTestId("blog-i-title"), "X");
    await user.click(screen.getByTestId("blog-submit"));
    await waitFor(() => expect(screen.getByTestId("blog-form-error")).toBeInTheDocument());
    expect(screen.getByTestId("blog-form")).toBeInTheDocument(); // still open
  });

  it("empty blog → empty state", async () => {
    primeReads([]);
    const user = userEvent.setup();
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("cv-tab")).toBeInTheDocument());
    await user.click(screen.getByTestId("tab-blog"));
    await waitFor(() => expect(screen.getByTestId("blog-empty")).toBeInTheDocument());
  });
});

describe("CAR-1 Career — Demo tab", () => {
  it("switches to demo tab and renders demo cards + status chip", async () => {
    primeReads([POST()], [ITEM(), ITEM({ id: "d2", name: "DevCrew", status: "wip" })]);
    const user = userEvent.setup();
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("cv-tab")).toBeInTheDocument());
    await user.click(screen.getByTestId("tab-demo"));
    await waitFor(() => expect(screen.getByTestId("demo-tab")).toBeInTheDocument());
    expect(screen.getByText("OutboundOS")).toBeInTheDocument();
    expect(screen.getByText("DevCrew")).toBeInTheDocument();
    expect(screen.getByTestId("demo-status-d2").textContent).toContain("wip");
  });

  it("delete-demo failure surfaces a write error (fail-closed)", async () => {
    primeReads([POST()], [ITEM()]);
    deleteCareerDemo.mockRejectedValue(new ApiError(500, "nope"));
    const user = userEvent.setup();
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("cv-tab")).toBeInTheDocument());
    await user.click(screen.getByTestId("tab-demo"));
    await waitFor(() => expect(screen.getByTestId("demo-card-d1")).toBeInTheDocument());
    await user.click(screen.getByTestId("demo-del-d1"));
    await waitFor(() => expect(screen.getByTestId("demo-write-error")).toBeInTheDocument());
  });
});

describe("CAR-1 Career — error state", () => {
  it("read failure → error state with retry", async () => {
    getCareerCv.mockRejectedValue(new ApiError(0, "network down"));
    getCareerBlog.mockRejectedValue(new ApiError(0, "network down"));
    getCareerDemo.mockRejectedValue(new ApiError(0, "network down"));
    render(<CareerPage />);
    await waitFor(() => expect(screen.getByTestId("career-error")).toBeInTheDocument());
  });
});
