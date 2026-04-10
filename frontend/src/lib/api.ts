import type { NewsletterSummary, NewsletterDetail, NewsletterInput } from "../features/newsletters/newsletter-types";

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

export type NewsletterPreview = {
  subject: string;
  preheader: string;
  html: string;
  plain_text: string;
  template_key: string;
};

export type NewsletterTestSendResult = {
  status: string;
  mode: string;
  message: string;
  provider_id: string | null;
  to_email: string;
};

export type RecipientSendOutcome = {
  email: string;
  status: string;
  provider_id: string | null;
  detail: string;
};

export type NewsletterSendResult = {
  status: string;
  mode: string;
  message: string;
  run: {
    id: number;
    newsletter_id: number;
    trigger_mode: string;
    run_status: string;
    provider_name: string;
    model_name: string;
    template_key: string;
    recipient_count: number;
    snapshot_subject: string;
  snapshot_preheader: string | null;
  snapshot_body_text: string;
  snapshot_recipient_emails: string;
  delivery_outcomes: string;
  result_mode: string | null;
  result_message: string | null;
  created_at: string;
  updated_at: string;
  };
  recipient_outcomes: RecipientSendOutcome[];
};

export type RunListResponse = {
  items: NewsletterSendResult["run"][];
};

export type RunDetailResponse = {
  run: NewsletterSendResult["run"];
  newsletter_snapshot: NewsletterSummary | null;
  recipient_emails: string[];
  recipient_outcomes: RecipientSendOutcome[];
  events: Array<{
    id: number;
    event_type: string;
    event_status: string;
    message: string;
    provider_id: string | null;
    created_at: string;
  }>;
};

export type NewsletterGenerationResult = {
  status: string;
  mode: string;
  message: string;
  newsletter: NewsletterDetail;
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

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function buildQueryString(params: Record<string, string | undefined>): string {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) {
      searchParams.set(key, value);
    }
  }
  const query = searchParams.toString();
  return query ? `?${query}` : "";
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
    }),
  listNewsletters: () => request<NewsletterSummary[]>("/newsletters"),
  getNewsletter: (newsletterId: number) =>
    request<NewsletterDetail>(`/newsletters/${newsletterId}`),
  previewNewsletter: (newsletterId: number) =>
    request<NewsletterPreview>(`/newsletters/${newsletterId}/preview`),
  generateNewsletter: (newsletterId: number) =>
    request<NewsletterGenerationResult>(`/newsletters/${newsletterId}/generate-draft`, {
      method: "POST"
    }),
  testSendNewsletter: (newsletterId: number, toEmail: string) =>
    request<NewsletterTestSendResult>(`/newsletters/${newsletterId}/test-send`, {
      method: "POST",
      jsonBody: { to_email: toEmail }
    }),
  sendNewsletter: (newsletterId: number) =>
    request<NewsletterSendResult>(`/newsletters/${newsletterId}/send`, {
      method: "POST"
    }),
  listRuns: (params: Record<string, string | undefined>) =>
    request<RunListResponse>(`/runs${buildQueryString(params)}`),
  getRunDetail: (runId: number) =>
    request<RunDetailResponse>(`/runs/${runId}`),
  reconcileRun: (runId: number) =>
    request<{ events: RunDetailResponse["events"] }>(`/runs/${runId}/reconcile`, {
      method: "POST"
    }),
  createNewsletter: (payload: NewsletterInput) =>
    request<NewsletterDetail>("/newsletters", {
      method: "POST",
      jsonBody: payload
    }),
  updateNewsletter: (newsletterId: number, payload: NewsletterInput) =>
    request<NewsletterDetail>(`/newsletters/${newsletterId}`, {
      method: "PUT",
      jsonBody: payload
    }),
  pauseNewsletter: (newsletterId: number) =>
    request<NewsletterDetail>(`/newsletters/${newsletterId}/pause`, {
      method: "POST"
    }),
  resumeNewsletterSchedule: (newsletterId: number) =>
    request<NewsletterDetail>(`/newsletters/${newsletterId}/schedule/resume`, {
      method: "POST"
    }),
  pauseNewsletterSchedule: (newsletterId: number) =>
    request<NewsletterDetail>(`/newsletters/${newsletterId}/schedule/pause`, {
      method: "POST"
    }),
  archiveNewsletter: (newsletterId: number) =>
    request<NewsletterDetail>(`/newsletters/${newsletterId}/archive`, {
      method: "POST"
    }),
  deleteNewsletter: (newsletterId: number) =>
    request<void>(`/newsletters/${newsletterId}`, {
      method: "DELETE"
    })
};
