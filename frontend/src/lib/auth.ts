/**
 * Client-side session: the login token and the user's name, kept in
 * sessionStorage (cleared when the tab closes). The backend checks the token
 * on every request; this module only remembers it.
 */

import type { UserInfo } from "@/lib/types";

const TOKEN_KEY = "overdraft-guard.token";
const USER_KEY = "overdraft-guard.user";
const CHANGE_EVENT = "overdraft-guard:session";

export type Session = { token: string; user: UserInfo };

let cached: { raw: string | null; session: Session | null } = { raw: null, session: null };

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const token = window.sessionStorage.getItem(TOKEN_KEY);
  const user = window.sessionStorage.getItem(USER_KEY);
  const raw = token && user ? `${token}\n${user}` : null;
  // Same object while nothing changed, as useSyncExternalStore requires.
  if (raw !== cached.raw) {
    let session: Session | null = null;
    if (token && user) {
      try {
        session = { token, user: JSON.parse(user) as UserInfo };
      } catch {
        session = null;
      }
    }
    cached = { raw, session };
  }
  return cached.session;
}

export function saveSession(session: Session): void {
  window.sessionStorage.setItem(TOKEN_KEY, session.token);
  window.sessionStorage.setItem(USER_KEY, JSON.stringify(session.user));
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function clearSession(): void {
  window.sessionStorage.removeItem(TOKEN_KEY);
  window.sessionStorage.removeItem(USER_KEY);
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/** For useSyncExternalStore: re-render when the session changes. */
export function subscribeSession(onChange: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}
