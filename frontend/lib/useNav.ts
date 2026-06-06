"use client";
/* ============================================================
   Router-safe nav hooks.
   next/navigation's useRouter() throws an invariant when no AppRouter
   provider is mounted (e.g. a unit test that renders a shell component in
   isolation). These wrappers read the context directly and degrade to a
   no-op router / "/" pathname instead of crashing — a defensive case
   (plan_sprint_0.md: "route not found", shell rendered without a router).
   In real app usage the provider is always present, so behavior is unchanged.
   ============================================================ */
import { useContext } from "react";
import {
  AppRouterContext,
  type AppRouterInstance,
} from "next/dist/shared/lib/app-router-context.shared-runtime";
import { PathnameContext } from "next/dist/shared/lib/hooks-client-context.shared-runtime";

const NOOP_ROUTER: AppRouterInstance = {
  push: () => {},
  replace: () => {},
  refresh: () => {},
  back: () => {},
  forward: () => {},
  prefetch: () => {},
};

/** useRouter() that never throws — returns a no-op router if unmounted. */
export function useSafeRouter(): AppRouterInstance {
  return useContext(AppRouterContext) ?? NOOP_ROUTER;
}

/** usePathname() that never throws — returns "/" if unmounted. */
export function useSafePathname(): string {
  return useContext(PathnameContext) ?? "/";
}
