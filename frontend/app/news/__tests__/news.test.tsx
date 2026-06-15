import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent, within } from "@testing-library/react";

const apiGet = vi.fn();
const apiPost = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, apiGet: (...a: unknown[]) => apiGet(...a), apiPost: (...a: unknown[]) => apiPost(...a) };
});

import NewsPage from "../page";
import { ApiError } from "@/lib/api";

function ok<T>(data: T) { return { success: true, data }; }
const DIGEST = { headline: "5 tin đáng chú ý", items: [{ title: "BTC up", source: "CoinDesk", url: "https://x/1", publishedTs: "2026-06-15T04:00:00+00:00", tags: ["CRYPTO"] }], count: 5, asOf: "2026-06-15T04:30:00+00:00" };
const LIST = { items: [{ id: 1, title: "Bitcoin two-week high", summary: "oil sliding", url: "https://x/2", source: "CoinDesk", publishedTs: "2026-06-15T03:56:00+00:00", tags: ["CRYPTO", "BTC"] }] };

/** route apiGet by URL: digest vs list, with optional per-endpoint failure. */
function routeGet({ digestFail = false, listFail = false } = {}) {
  apiGet.mockImplementation((path: string) => {
    if (path.startsWith("/news/digest")) return digestFail ? Promise.reject(new ApiError(500, "digest down")) : Promise.resolve(ok(DIGEST));
    return listFail ? Promise.reject(new ApiError(500, "list down")) : Promise.resolve(ok(LIST));
  });
}

describe("News view (FE-5)", () => {
  beforeEach(() => { apiGet.mockReset(); apiPost.mockReset(); });

  it("renders digest + headline list (each item a clickable source link)", async () => {
    routeGet();
    render(<NewsPage />);
    await waitFor(() => expect(screen.getByTestId("news-screen")).toBeInTheDocument());
    expect(screen.getByTestId("news-digest-headline")).toHaveTextContent("5 tin");
    expect(screen.getByTestId("news-digest-row")).toHaveAttribute("href", "https://x/1");
    expect(screen.getByTestId("news-row-link")).toHaveAttribute("href", "https://x/2");
  });

  it("PER-PANEL ISOLATION: digest errors but list still renders (page alive)", async () => {
    routeGet({ digestFail: true });
    render(<NewsPage />);
    await waitFor(() => expect(screen.getByTestId("news-digest-error")).toBeInTheDocument());
    // list panel unaffected
    expect(screen.getByTestId("news-row")).toBeInTheDocument();
    expect(screen.getByTestId("news-screen")).toBeInTheDocument();
  });

  it("PER-PANEL ISOLATION: list errors but digest still renders", async () => {
    routeGet({ listFail: true });
    render(<NewsPage />);
    await waitFor(() => expect(screen.getByTestId("news-list-error")).toBeInTheDocument());
    expect(screen.getByTestId("news-digest-row")).toBeInTheDocument();
  });

  it("tag filter → refetches with the tag", async () => {
    routeGet();
    render(<NewsPage />);
    await waitFor(() => expect(screen.getByTestId("news-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("news-tag-BTC"));
    await waitFor(() => expect(apiGet.mock.calls.some((c) => String(c[0]).includes("tag=BTC"))).toBe(true));
  });

  it("capture now → POST /news/capture + success notice + refetch", async () => {
    routeGet();
    apiPost.mockResolvedValueOnce(ok({ new: 3, total: 42 }));
    render(<NewsPage />);
    await waitFor(() => expect(screen.getByTestId("news-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("news-capture"));
    await waitFor(() => expect(apiPost).toHaveBeenCalledWith("/news/capture", {}));
    await waitFor(() => expect(screen.getByTestId("news-capture-ok")).toHaveTextContent("3"));
  });

  it("FAIL-CLOSED: capture error → inline error, page stays alive", async () => {
    routeGet();
    apiPost.mockRejectedValueOnce(new ApiError(500, "capture failed"));
    render(<NewsPage />);
    await waitFor(() => expect(screen.getByTestId("news-screen")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("news-capture"));
    await waitFor(() => expect(screen.getByTestId("news-capture-error")).toHaveTextContent("capture failed"));
    expect(screen.getByTestId("news-screen")).toBeInTheDocument();
  });

  it("empty digest → honest empty (not blank)", async () => {
    apiGet.mockImplementation((path: string) =>
      path.startsWith("/news/digest") ? Promise.resolve(ok({ headline: "", items: [], count: 0, asOf: "" })) : Promise.resolve(ok({ items: [] })),
    );
    render(<NewsPage />);
    await waitFor(() => expect(screen.getByTestId("news-digest-empty")).toBeInTheDocument());
    expect(screen.getByTestId("news-list-empty")).toBeInTheDocument();
  });
});
