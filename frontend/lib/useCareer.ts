"use client";
/* ============================================================
   useCareer — CAR-1 career cockpit data + WRITE operations.
   Three resources behind the /career tab: living CV (read + edit), blog posts
   (CRUD), demo showcase (CRUD). REFETCH-AFTER-WRITE + FAIL-CLOSED (a failed
   POST/PUT/DELETE throws to the caller — the change is never shown as saved).

   Mirrors the frozen backend modules/career/schema.py (Cv/BlogPost/DemoItem).
   ============================================================ */
import { useCallback, useEffect, useState } from "react";
import {
  getCareerCv,
  getCareerCvRaw,
  updateCareerCv,
  getCareerBlog,
  createCareerBlog,
  updateCareerBlog,
  deleteCareerBlog,
  getCareerDemo,
  createCareerDemo,
  updateCareerDemo,
  deleteCareerDemo,
  ApiError,
} from "@/lib/api";
import type { Cv, BlogPost, BlogInput, DemoItem, DemoInput } from "@/lib/types";

export type CareerStatus = "loading" | "error" | "ready";

export interface UseCareer {
  cv: Cv | null;
  blog: BlogPost[];
  demo: DemoItem[];
  status: CareerStatus;
  errMsg: string;
  warning: string | null;
  reload: () => void;
  // CV
  editCv: (markdown: string) => Promise<void>;
  fetchCvRaw: () => Promise<string>;
  // Blog
  createBlog: (input: BlogInput) => Promise<void>;
  updateBlog: (id: string, input: BlogInput) => Promise<void>;
  deleteBlog: (id: string) => Promise<void>;
  // Demo
  createDemo: (input: DemoInput) => Promise<void>;
  updateDemo: (id: string, input: DemoInput) => Promise<void>;
  deleteDemo: (id: string) => Promise<void>;
}

export function useCareer(): UseCareer {
  const [cv, setCv] = useState<Cv | null>(null);
  const [blog, setBlog] = useState<BlogPost[]>([]);
  const [demo, setDemo] = useState<DemoItem[]>([]);
  const [status, setStatus] = useState<CareerStatus>("loading");
  const [errMsg, setErrMsg] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let alive = true;
    setStatus("loading");
    (async () => {
      try {
        const [cvRes, blogRes, demoRes] = await Promise.all([
          getCareerCv(),
          getCareerBlog(),
          getCareerDemo(),
        ]);
        if (!alive) return;
        setCv(cvRes?.data ?? null);
        setBlog(Array.isArray(blogRes?.data) ? blogRes.data : []);
        setDemo(Array.isArray(demoRes?.data) ? demoRes.data : []);
        setWarning(blogRes?.warning ?? demoRes?.warning ?? null);
        setStatus("ready");
      } catch (e) {
        if (!alive) return;
        setErrMsg(e instanceof ApiError ? e.message : (e as Error).message);
        setStatus("error");
      }
    })();
    return () => {
      alive = false;
    };
  }, [nonce]);

  // CV
  const editCv = useCallback(
    async (markdown: string) => {
      await updateCareerCv(markdown);
      reload();
    },
    [reload],
  );
  const fetchCvRaw = useCallback(async () => {
    const res = await getCareerCvRaw();
    return res?.data?.markdown ?? "";
  }, []);

  // Blog
  const createBlog = useCallback(
    async (input: BlogInput) => {
      await createCareerBlog(input);
      reload();
    },
    [reload],
  );
  const updateBlog = useCallback(
    async (id: string, input: BlogInput) => {
      await updateCareerBlog(id, input);
      reload();
    },
    [reload],
  );
  const deleteBlog = useCallback(
    async (id: string) => {
      await deleteCareerBlog(id);
      reload();
    },
    [reload],
  );

  // Demo
  const createDemo = useCallback(
    async (input: DemoInput) => {
      await createCareerDemo(input);
      reload();
    },
    [reload],
  );
  const updateDemo = useCallback(
    async (id: string, input: DemoInput) => {
      await updateCareerDemo(id, input);
      reload();
    },
    [reload],
  );
  const deleteDemo = useCallback(
    async (id: string) => {
      await deleteCareerDemo(id);
      reload();
    },
    [reload],
  );

  return {
    cv, blog, demo, status, errMsg, warning, reload,
    editCv, fetchCvRaw,
    createBlog, updateBlog, deleteBlog,
    createDemo, updateDemo, deleteDemo,
  };
}
