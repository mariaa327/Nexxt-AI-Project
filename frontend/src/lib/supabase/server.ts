import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

import { getSupabaseConfig } from "./config";

/**
 * Create a Supabase client for Server Components, Server Actions and Route
 * Handlers.
 *
 * Next.js's `cookies()` is asynchronous in current versions, so this function
 * is async. Cookie writes throw inside Server Components (where the response
 * headers are already committed); those errors are intentionally ignored
 * because the proxy is responsible for persisting refreshed sessions.
 *
 * Returns `null` when Supabase is not configured.
 */
export async function getSupabaseServerClient(): Promise<SupabaseClient | null> {
  const config = getSupabaseConfig();
  if (!config) {
    return null;
  }

  const cookieStore = await cookies();

  return createServerClient(config.url, config.key, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Called from a Server Component, where cookies are read-only.
          // The proxy refreshes the session and writes the cookies instead.
        }
      },
    },
  });
}
