import type { NewsletterSummary, NewsletterDetail, NewsletterInput } from "../features/newsletters/newsletter-types";
import type { EmailTemplateSummary, EmailTemplateDetail, EmailTemplateInput } from "../features/templates/template-types";
import type { ProviderSummary, ProviderDetail, ProviderInput, ProviderPreset } from "../features/providers/provider-types";
import type { ApiKeySummary, ApiKeyDetail, ApiKeyInput } from "../features/api-keys/api-key-types";
import type {
  AuditEventListParams,
  AuditEventListResponse,
  OperationalEventListParams,
  OperationalEventListResponse
} from "../features/audit/audit-types";

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
    revision_id: number | null;
    run_type: string | null;
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
  revision_id?: number | null;
  newsletter: NewsletterDetail;
  run: NewsletterSendResult["run"];
};

export type DraftRevisionSummary = {
  id: number;
  newsletter_id: number;
  version_number: number;
  state: string;
  origin: string;
  subject: string;
  preheader: string | null;
  body_text: string;
  generation_run_id: number | null;
  created_at: string;
  updated_at: string;
};

export type DraftRevisionListResponse = {
  items: DraftRevisionSummary[];
};

export type DraftRevisionApproveResponse = {
  revision: DraftRevisionSummary;
  newsletter: NewsletterDetail;
};



export type FormOptionTemplate = {
  key: string;
  name: string;
  is_system: boolean;
};

export type FormOptionProvider = {
  id: number;
  name: string;
  provider_type: string;
  default_model: string | null;
};

export type FormOptionApiKey = {
  id: number;
  name: string;
  provider_type: string;
  masked_key: string;
  from_email: string | null;
};

export type FormOptions = {
  templates: FormOptionTemplate[];
  providers: FormOptionProvider[];
  models: Record<string, string[]>;
  api_keys: FormOptionApiKey[];
  timezones: string[];
};

export type ProviderModelsResponse = {
  models: string[];
  default_model: string | null;
  verified_model: string | null;
  verification_message: string | null;
};

export type ProviderTestResponse = {
  status: string;
  message: string;
  provider_type: string;
  default_model: string | null;
  has_active_api_key: boolean;
};

export type ApiKeyTestResponse = {
  status: string;
  message: string;
  provider_type: string;
  masked_key: string;
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
  bootstrap: (email: string, password: string, bootstrapSecret?: string) =>
    request<SessionResponse>("/auth/bootstrap", {
      method: "POST",
      jsonBody: { email, password, bootstrap_secret: bootstrapSecret }
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
  previewNewsletterRevision: (newsletterId: number, revisionId: number) =>
    request<NewsletterPreview>(`/newsletters/${newsletterId}/revisions/${revisionId}/preview`),
  generateNewsletter: (newsletterId: number) =>
    request<NewsletterGenerationResult>(`/newsletters/${newsletterId}/generate-draft`, {
      method: "POST"
    }),
  listNewsletterRevisions: (newsletterId: number) =>
    request<DraftRevisionListResponse>(`/newsletters/${newsletterId}/revisions`),
  approveNewsletterRevision: (newsletterId: number, revisionId: number) =>
    request<DraftRevisionApproveResponse>(`/newsletters/${newsletterId}/revisions/${revisionId}/approve`, {
      method: "POST"
    }),

  testSendNewsletter: (newsletterId: number, toEmail: string) =>
    request<NewsletterTestSendResult>(`/newsletters/${newsletterId}/test-send`, {
      method: "POST",
      jsonBody: { to_email: toEmail }
    }),
  testSendNewsletterRevision: (newsletterId: number, revisionId: number, toEmail: string) =>
    request<NewsletterTestSendResult>(`/newsletters/${newsletterId}/revisions/${revisionId}/test-send`, {
      method: "POST",
      jsonBody: { to_email: toEmail }
    }),
  sendNewsletter: (newsletterId: number, idempotencyKey?: string) =>
    request<NewsletterSendResult>(`/newsletters/${newsletterId}/send`, {
      method: "POST",
      jsonBody: idempotencyKey ? { idempotency_key: idempotencyKey } : undefined,
    }),
  sendNewsletterRevision: (newsletterId: number, revisionId: number, idempotencyKey?: string) =>
    request<NewsletterSendResult>(`/newsletters/${newsletterId}/revisions/${revisionId}/send`, {
      method: "POST",
      jsonBody: idempotencyKey ? { idempotency_key: idempotencyKey } : undefined,
    }),
  listAuditEvents: (params: AuditEventListParams) =>
    request<AuditEventListResponse>(`/audit${buildQueryString(params)}`),
  listOperationalEvents: (params: OperationalEventListParams) =>
    request<OperationalEventListResponse>(`/runs/events${buildQueryString(params)}`),
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
    }),

  formOptions: () => request<FormOptions>("/newsletters/form-options"),

  emailTemplates: {
    list: () => request<EmailTemplateSummary[]>("/email-templates"),
    get: (templateId: number) =>
      request<EmailTemplateDetail>(`/email-templates/${templateId}`),
    create: (payload: EmailTemplateInput) =>
      request<EmailTemplateDetail>("/email-templates", {
        method: "POST",
        jsonBody: payload
      }),
    update: (templateId: number, payload: EmailTemplateInput) =>
      request<EmailTemplateDetail>(`/email-templates/${templateId}`, {
        method: "PUT",
        jsonBody: payload
      }),
    delete: (templateId: number) =>
      request<void>(`/email-templates/${templateId}`, {
        method: "DELETE"
      }),
    preview: (templateId: number, variables?: Record<string, string>) =>
      request<{ html: string }>(`/email-templates/${templateId}/preview`, {
        method: "POST",
        jsonBody: variables ? { variables } : undefined
      }),
    previewLive: (htmlTemplate: string) =>
      request<{ html: string }>("/email-templates/preview-live", {
        method: "POST",
        jsonBody: { html_template: htmlTemplate, variables: {} }
      }),
    listPresets: () => request<Array<{ key: string; name: string; description: string; html_template: string }>>("/email-templates/presets/list"),
    setDefault: (templateId: number) =>
      request<EmailTemplateDetail>(`/email-templates/${templateId}/set-default`, {
        method: "POST"
      })
  },

  providers: {
    list: () => request<ProviderSummary[]>("/providers"),
    listPresets: () => request<ProviderPreset[]>("/providers/presets/list"),
    get: (providerId: number) =>
      request<ProviderDetail>(`/providers/${providerId}`),
    create: (payload: ProviderInput) =>
      request<ProviderDetail>("/providers", {
        method: "POST",
        jsonBody: payload
      }),
    update: (providerId: number, payload: ProviderInput) =>
      request<ProviderDetail>(`/providers/${providerId}`, {
        method: "PUT",
        jsonBody: payload
      }),
    delete: (providerId: number) =>
      request<void>(`/providers/${providerId}`, {
        method: "DELETE"
      }),
    getModels: (providerId: number) =>
      request<ProviderModelsResponse>(`/providers/${providerId}/models`),
    listPresetModels: (providerType: string) =>
      request<ProviderModelsResponse>(`/providers/presets/${providerType}/models`),
    test: (providerId: number) =>
      request<ProviderTestResponse>(`/providers/${providerId}/test`, {
        method: "POST"
      })
  },

  apiKeys: {
    list: () => request<ApiKeySummary[]>("/api-keys"),
    get: (apiKeyId: number) =>
      request<ApiKeyDetail>(`/api-keys/${apiKeyId}`),
    create: (payload: ApiKeyInput) =>
      request<ApiKeyDetail>("/api-keys", {
        method: "POST",
        jsonBody: payload
      }),
    update: (apiKeyId: number, payload: ApiKeyInput) =>
      request<ApiKeyDetail>(`/api-keys/${apiKeyId}`, {
        method: "PUT",
        jsonBody: payload
      }),
    delete: (apiKeyId: number) =>
      request<void>(`/api-keys/${apiKeyId}`, {
        method: "DELETE"
      }),
    test: (apiKeyId: number) =>
      request<ApiKeyTestResponse>(`/api-keys/${apiKeyId}/test`, {
        method: "POST"
      })
  }
};
