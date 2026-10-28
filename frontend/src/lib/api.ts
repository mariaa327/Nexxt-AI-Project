import type {
  AnalyzeResponse,
  BillDecision,
  Challenge,
  ExecuteResponse,
  OptionId,
  DemoUser,
  LoginResponse,
  UserInfo,
} from "@/lib/types";
import { clearSession, getSession } from "@/lib/auth";

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
  signal?: AbortSignal;
};

/**
 * Typed wrapper around `fetch` for the FastAPI backend.
 *
 * Sets JSON headers, attaches the session token, and converts network, HTTP and parsing failures into
 * `ApiError` instances with readable messages.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal } = options;

  const headers: Record<string, string> = { Accept: "application/json" };
  const session = getSession();
  if (session) {
    headers.Authorization = `Bearer ${session.token}`;
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

  if (response.status === 401 && session) {
    // Expired or invalid session: forget it; pages listening for the change
    // send the user back to the login page.
    clearSession();
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

/** Deterministic picture: balances, upcoming payments, projection, options. */
export function getDashboard(signal?: AbortSignal): Promise<BillDecision> {
  return apiRequest<BillDecision>("/dashboard", { signal });
}

/** Engine decision plus the recommendation phrased by the model (or rules). */
export function analyze(signal?: AbortSignal): Promise<AnalyzeResponse> {
  return apiRequest<AnalyzeResponse>("/agent/analyze", { method: "POST", signal });
}

/** Apply an option to the demo client (simulated, in memory). */
/** Start payment verification for an option (simulated banking-app approval). */
export function initiateExecution(optionId: OptionId): Promise<Challenge> {
  return apiRequest<Challenge>("/agent/execute/initiate", {
    method: "POST",
    body: { option_id: optionId },
  });
}

export function getChallenge(challengeId: string, signal?: AbortSignal): Promise<Challenge> {
  return apiRequest<Challenge>(`/agent/challenges/${encodeURIComponent(challengeId)}`, {
    signal,
  });
}

export function cancelChallenge(challengeId: string): Promise<Challenge> {
  return apiRequest<Challenge>(
    `/agent/challenges/${encodeURIComponent(challengeId)}/cancel`,
    { method: "POST" },
  );
}

/** Apply the option of an approved verification (simulated, in memory). */
export function executeOption(challengeId: string): Promise<ExecuteResponse> {
  return apiRequest<ExecuteResponse>("/agent/execute", {
    method: "POST",
    body: { challenge_id: challengeId },
  });
}

/** Restore the logged-in user's original demo data. */
export function resetDemo(): Promise<BillDecision> {
  return apiRequest<BillDecision>("/agent/reset", { method: "POST" });
}

// --- Login -----------------------------------------------------------------

export function login(username: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export function getMe(signal?: AbortSignal): Promise<UserInfo> {
  return apiRequest<UserInfo>("/auth/me", { signal });
}

/** Fictional demo accounts, shown on the login page. */
export function getDemoUsers(signal?: AbortSignal): Promise<DemoUser[]> {
  return apiRequest<DemoUser[]>("/auth/demo-users", { signal });
}
