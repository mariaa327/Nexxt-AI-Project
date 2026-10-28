"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { getSupabaseConfig, SUPABASE_CONFIG_ERROR_MESSAGE } from "./config";

/**
 * Return the browser Supabase client, or `null` when Supabase is not
 * configured.
 *
 * `createBrowserClient` already caches a single instance internally, so calling
 * this repeatedly is cheap and does not create extra clients.
 */
export function getSupabaseBrowserClient(): SupabaseClient | null {
  const config = getSupabaseConfig();
  if (!config) {
    return null;
  }

  return createBrowserClient(config.url, config.key);
}

/** Like `getSupabaseBrowserClient`, but throws a readable error when unset. */
export function requireSupabaseBrowserClient(): SupabaseClient {
  const client = getSupabaseBrowserClient();
  if (!client) {
    throw new Error(SUPABASE_CONFIG_ERROR_MESSAGE);
  }
  return client;
}
