import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { getSupabaseConfig } from "@/lib/supabase/config";

/**
 * Refresh the Supabase session on every matched request.
 *
 * The proxy only refreshes tokens and copies the resulting cookies onto both
 * the request (so Server Components see the new session) and the response (so
 * the browser stores it). It is *not* the authorization layer: the FastAPI
 * backend verifies the JWT independently for every protected call.
 */
export async function proxy(request: NextRequest) {
  const config = getSupabaseConfig();
  if (!config) {
    // Local development without Supabase credentials: let every request
    // through so the landing page still renders.
    return NextResponse.next({ request });
  }

  let response = NextResponse.next({ request });

  const supabase = createServerClient(config.url, config.key, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
        // Cache headers keep a CDN from serving one user's refreshed token to
        // another user.
        for (const [key, value] of Object.entries(headers)) {
          response.headers.set(key, value);
        }
      },
    },
  });

  // getClaims() verifies the token signature (against cached JWKS keys for
  // asymmetric signing) and refreshes the session when it is close to expiry.
  // Never use getSession() here: it does not revalidate the token.
  await supabase.auth.getClaims();

  return response;
}

export const config = {
  matcher: [
    /*
     * Run on everything except Next.js internals and static assets, so auth
     * logic never blocks CSS, JS or images.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
