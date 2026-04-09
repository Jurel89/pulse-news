export type UserSummary = {
  id: number;
  email: string;
  created_at: string;
  updated_at: string;
};

export type SessionResponse = {
  initialized: boolean;
  authenticated: boolean;
  user: UserSummary | null;
};

type ApiRequestInit = Omit<RequestInit, "body"> & {
  jsonBody?: unknown;
};

async function request<T>(path: string, init?: ApiRequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.jsonBody !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: "include",
    body: init?.jsonBody !== undefined ? JSON.stringify(init.jsonBody) : undefined
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Request failed." }));
    throw new Error(payload.detail ?? "Request failed.");
  }

  return (await response.json()) as T;
}

export const api = {
  getSession: () => request<SessionResponse>("/auth/session"),
  bootstrap: (email: string, password: string) =>
    request<SessionResponse>("/auth/bootstrap", {
      method: "POST",
      jsonBody: { email, password }
    }),
  login: (email: string, password: string) =>
    request<SessionResponse>("/auth/login", {
      method: "POST",
      jsonBody: { email, password }
    }),
  logout: () =>
    request<{ message: string }>("/auth/logout", {
      method: "POST"
    }),
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ message: string }>("/auth/change-password", {
      method: "POST",
      jsonBody: { current_password: currentPassword, new_password: newPassword }
    })
};
