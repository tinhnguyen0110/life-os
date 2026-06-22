import { apiGet, apiPost, apiPut, apiDelete } from "./_client";
import type {
  ApiResponse,
  BlogInput,
  BlogPost,
  Cv,
  DemoInput,
  DemoItem,
} from "@/lib/types";

/** The living CV, parsed into header meta + ordered sections (with proof chips). */
export function getCareerCv(): Promise<ApiResponse<Cv>> {
  return apiGet<Cv>("/career/cv");
}
/** The CV's raw markdown (for export / copy). */
export function getCareerCvRaw(): Promise<ApiResponse<{ markdown: string }>> {
  return apiGet<{ markdown: string }>("/career/cv/raw");
}
/** Replace the CV's raw markdown (edit). Returns the re-parsed CV. 422 on empty. */
export function updateCareerCv(markdown: string): Promise<ApiResponse<Cv>> {
  return apiPut<Cv>("/career/cv", { markdown });
}
/** All blog posts, newest-updated first. */
export function getCareerBlog(): Promise<ApiResponse<BlogPost[]>> {
  return apiGet<BlogPost[]>("/career/blog");
}
/** Create a blog post. Bad field → ApiError(422) per-field. */
export function createCareerBlog(body: BlogInput): Promise<ApiResponse<BlogPost>> {
  return apiPost<BlogPost>("/career/blog", body);
}
/** Update a blog post (404 if absent). */
export function updateCareerBlog(id: string, body: BlogInput): Promise<ApiResponse<BlogPost>> {
  return apiPut<BlogPost>(`/career/blog/${encodeURIComponent(id)}`, body);
}
/** Delete a blog post (404 if absent). */
export function deleteCareerBlog(id: string): Promise<ApiResponse<{ deleted: string }>> {
  return apiDelete<{ deleted: string }>(`/career/blog/${encodeURIComponent(id)}`);
}
/** All demo / showcase items, newest-updated first. */
export function getCareerDemo(): Promise<ApiResponse<DemoItem[]>> {
  return apiGet<DemoItem[]>("/career/demo");
}
/** Create a demo item. Bad field → ApiError(422) per-field. */
export function createCareerDemo(body: DemoInput): Promise<ApiResponse<DemoItem>> {
  return apiPost<DemoItem>("/career/demo", body);
}
/** Update a demo item (404 if absent). */
export function updateCareerDemo(id: string, body: DemoInput): Promise<ApiResponse<DemoItem>> {
  return apiPut<DemoItem>(`/career/demo/${encodeURIComponent(id)}`, body);
}
/** Delete a demo item (404 if absent). */
export function deleteCareerDemo(id: string): Promise<ApiResponse<{ deleted: string }>> {
  return apiDelete<{ deleted: string }>(`/career/demo/${encodeURIComponent(id)}`);
}

/* ---- Decision tower (FINANCE-ASSISTANT P1–P4) — the /decision cockpit ---- */
