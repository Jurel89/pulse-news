export type NewsletterSummary = {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  prompt: string;
  draft_subject: string;
  draft_preheader: string | null;
  draft_body_text: string;
  provider_name: string;
  model_name: string;
  template_key: string;
  audience_name: string;
  delivery_topic: string;
  timezone: string;
  schedule_cron: string | null;
  schedule_enabled: boolean;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type NewsletterDetail = NewsletterSummary & {
  recipient_import_text: string;
  recipients: Array<{
    id: number;
    email: string;
    is_active: boolean;
    unsubscribe_token: string;
    unsubscribed_at: string | null;
    suppression_reason: string | null;
  }>;
};

export type Newsletter = NewsletterSummary;

export type NewsletterInput = {
  name: string;
  description: string;
  prompt: string;
  draft_subject: string;
  draft_preheader: string;
  draft_body_text: string;
  provider_name: string;
  model_name: string;
  template_key: string;
  audience_name: string;
  delivery_topic: string;
  timezone: string;
  schedule_cron: string;
  schedule_enabled: boolean;
  status: string;
  notes: string;
  recipient_import_text: string;
};

export const emptyNewsletterInput: NewsletterInput = {
  name: "",
  description: "",
  prompt: "",
  draft_subject: "",
  draft_preheader: "",
  draft_body_text: "",
  provider_name: "openai",
  model_name: "gpt-4o-mini",
  template_key: "signal",
  audience_name: "default-audience",
  delivery_topic: "default-topic",
  timezone: "UTC",
  schedule_cron: "",
  schedule_enabled: false,
  status: "draft",
  notes: "",
  recipient_import_text: "",
};

export function toNewsletterInput(detail: NewsletterDetail): NewsletterInput {
  return {
    name: detail.name,
    description: detail.description ?? "",
    prompt: detail.prompt,
    draft_subject: detail.draft_subject,
    draft_preheader: detail.draft_preheader ?? "",
    draft_body_text: detail.draft_body_text,
    provider_name: detail.provider_name,
    model_name: detail.model_name,
    template_key: detail.template_key,
    audience_name: detail.audience_name,
    delivery_topic: detail.delivery_topic,
    timezone: detail.timezone,
    schedule_cron: detail.schedule_cron ?? "",
    schedule_enabled: detail.schedule_enabled,
    status: detail.status,
    notes: detail.notes ?? "",
    recipient_import_text: detail.recipient_import_text,
  };
}
