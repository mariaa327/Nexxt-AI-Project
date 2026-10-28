/**
 * Centralised access to the public Supabase configuration.
 *
 * Only `NEXT_PUBLIC_` variables are read here: they are embedded in the browser
 * bundle and are therefore public by definition. Server-side secrets (the
 * database URL, the JWT secret, the AI provider key) must never appear in this
 * file or in any `NEXT_PUBLIC_` variable.
 */

export type SupabaseConfig = {
  url: string;
  key: string;
};

/**
 * Read the Supabase URL and public key.
 *
 * Returns `null` when the app is running without Supabase configured (for
 * example a fresh clone with an empty `.env.local`). Callers surface a friendly
 * setup message instead of crashing at import time.
 */
export function getSupabaseConfig(): SupabaseConfig | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  // The publishable key is the current name; the anon key is kept as a
  // compatibility fallback for older projects.
  const key =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() ||
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();

  if (!url || !key) {
    return null;
  }

  return { url, key };
}

export const SUPABASE_CONFIG_ERROR_MESSAGE =
  "Supabase is not configured. Copy frontend/.env.example to frontend/.env.local and set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY, then restart the dev server.";
