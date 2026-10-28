import type { AgentOutput } from "@/lib/types";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Base URL of the FastAPI backend, including the `/api` prefix.
 * Override with NEXT_PUBLIC_API_URL; the fallback is the documented local
 * development default.
 */
const DEFAULT_API_URL = "http://localhost:8000/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Join a base URL and a path without duplicate or missing slashes. */
export function joinUrl(base: string, path: string): string {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.trim();
  return (configured || DEFAULT_API_URL).replace(/\/+$/, "");
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Skip attaching the Supabase access token (public endpoints). */
  anonymous?: boolean;
  signal?: AbortSignal;
};

async function getAccessToken(): Promise<string | null> {
  const supabase = getSupabaseBrowserClient();
  if (!supabase) {
    return null;
  }

  const { data, error } = await supabase.auth.getSession();
  if (error) {
    throw new ApiError("Could not read your Supabase session. Please sign in again.", 401);
  }
  return data.session?.access_token ?? null;
}

/**
 * Typed wrapper around `fetch` for the FastAPI backend.
 *
 * Attaches the current Supabase access token, sets JSON headers, and converts
 * network, HTTP and parsing failures into `ApiError` instances with readable
 * messages.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, anonymous = false, signal } = options;

  const headers: Record<string, string> = { Accept: "application/json" };

  if (!anonymous) {
    const token = await getAccessToken();
    if (!token) {
      throw new ApiError("You need to sign in before using this feature.", 401);
    }
    headers.Authorization = `Bearer ${token}`;
  }

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  let response: Response;
  try {
    response = await fetch(joinUrl(getApiBaseUrl(), path), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError(
      "Could not reach the backend API. Check that it is running and that NEXT_PUBLIC_API_URL is correct.",
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await extractErrorMessage(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError("The backend returned an invalid JSON response.", response.status);
  }
}

/** Turn FastAPI's error body into a single readable sentence. */
async function extractErrorMessage(response: Response): Promise<string> {
  const fallback = `Request failed with status ${response.status}.`;

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return fallback;
  }

  if (typeof payload !== "object" || payload === null) {
    return fallback;
  }

  const detail = (payload as { detail?: unknown }).detail;

  if (typeof detail === "string") {
    return detail;
  }

  // FastAPI validation errors: [{ loc, msg, type }, ...]
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return null;
      })
      .filter((message): message is string => Boolean(message));

    if (messages.length > 0) {
      return messages.join(" ");
    }
  }

  return fallback;
}

// --- Typed API functions ---------------------------------------------------

export type AgentRunResponse = {
  id: string;
  result: AgentOutput;
  created_at: string;
};

/** Run the AI agent. Requires a signed-in Supabase user. */
export function runAgent(prompt: string, signal?: AbortSignal): Promise<AgentRunResponse> {
  return apiRequest<AgentRunResponse>("/agent/run", {
    method: "POST",
    body: { prompt },
    signal,
  });
}
