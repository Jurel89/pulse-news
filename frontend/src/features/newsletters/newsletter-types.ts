export type Newsletter = {
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
  timezone: string;
  schedule_cron: string | null;
  schedule_enabled: boolean;
  status: string;
  notes: string | null;
  recipient_import_text: string;
  recipients: Array<{
    id: number;
    email: string;
    is_active: boolean;
    unsubscribe_token: string;
  }>;
  created_at: string;
  updated_at: string;
};

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
  timezone: "UTC",
  schedule_cron: "",
  schedule_enabled: false,
  status: "draft",
  notes: "",
  recipient_import_text: ""
};

export function toNewsletterInput(newsletter: Newsletter): NewsletterInput {
  return {
    name: newsletter.name,
    description: newsletter.description ?? "",
    prompt: newsletter.prompt,
    draft_subject: newsletter.draft_subject,
    draft_preheader: newsletter.draft_preheader ?? "",
    draft_body_text: newsletter.draft_body_text,
    provider_name: newsletter.provider_name,
    model_name: newsletter.model_name,
    template_key: newsletter.template_key,
    audience_name: newsletter.audience_name,
    timezone: newsletter.timezone,
    schedule_cron: newsletter.schedule_cron ?? "",
    schedule_enabled: newsletter.schedule_enabled,
    status: newsletter.status,
    notes: newsletter.notes ?? "",
    recipient_import_text: newsletter.recipient_import_text
  };
}
