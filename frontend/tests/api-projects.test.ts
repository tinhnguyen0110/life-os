/**
 * tests/api-projects.test.ts — Sprint 1 S2-T1 unit tests for the new project
 * API client functions (getProjects, getProject, apiPost). Asserts the request
 * shape (method/url/body) and envelope/error handling — observable behavior,
 * not call-count theater.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { getProjects, getProject, apiPost, ApiError, apiBase } from "@/lib/api";

function mockFetchOnce(body: unknown, { ok = true, status = 200 } = {}) {
  const fn = vi.fn().mockResolvedValueOnce({
    ok,
    status,
    json: async () => body,
  } as Response);
  global.fetch = fn as unknown as typeof fetch;
  return fn;
}

afterEach(() => vi.restoreAllMocks());

describe("getProjects()", () => {
  it("GETs /projects and returns the {projects, summary} envelope", async () => {
    const payload = {
      success: true,
      data: { projects: [], summary: { act: 0, slow: 0, stall: 0, dead: 0, total: 0 } },
    };
    const fn = mockFetchOnce(payload);
    const res = await getProjects();
    expect(fn).toHaveBeenCalledWith(`${apiBase}/projects`, expect.anything());
    expect(res.data.summary.total).toBe(0);
    expect(Array.isArray(res.data.projects)).toBe(true);
  });
});

describe("getProject(id)", () => {
  it("GETs /projects/{id} (url-encoded) and returns the status", async () => {
    const payload = { success: true, data: { id: "my-proj", name: "My Proj" } };
    const fn = mockFetchOnce(payload);
    const res = await getProject("my-proj");
    expect(fn).toHaveBeenCalledWith(`${apiBase}/projects/my-proj`, expect.anything());
    expect(res.data.id).toBe("my-proj");
  });

  it("url-encodes ids with special characters", async () => {
    const fn = mockFetchOnce({ success: true, data: { id: "a/b" } });
    await getProject("a/b").catch(() => null);
    expect(fn).toHaveBeenCalledWith(`${apiBase}/projects/a%2Fb`, expect.anything());
  });

  it("throws ApiError(404) when the project is not found", async () => {
    mockFetchOnce({ detail: "project 'x' not found" }, { ok: false, status: 404 });
    await expect(getProject("x")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
    });
  });
});

describe("apiPost()", () => {
  it("POSTs JSON body with the right method + content-type", async () => {
    const fn = mockFetchOnce({ success: true, data: { id: "new" } });
    await apiPost("/projects", { name: "New", repo: "/r" });
    const [, init] = fn.mock.calls[0];
    expect(init.method).toBe("POST");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ name: "New", repo: "/r" });
  });

  it("surfaces backend `detail` as the ApiError message on 409", async () => {
    mockFetchOnce({ detail: "id already exists" }, { ok: false, status: 409 });
    await expect(apiPost("/projects", {})).rejects.toThrow(/already exists/);
  });

  it("wraps network failures in ApiError(0)", async () => {
    global.fetch = vi.fn().mockRejectedValueOnce(new Error("ECONNREFUSED")) as never;
    await expect(apiPost("/projects", {})).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
    });
  });

  it("sends no body when none provided", async () => {
    const fn = mockFetchOnce({ success: true, data: {} });
    await apiPost("/projects/x/refresh");
    const [, init] = fn.mock.calls[0];
    expect(init.body).toBeUndefined();
  });

  it("is exported alongside ApiError", () => {
    expect(typeof apiPost).toBe("function");
    expect(ApiError).toBeTruthy();
  });
});
