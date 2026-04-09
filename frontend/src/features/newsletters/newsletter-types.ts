export type Newsletter = {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  prompt: string;
  provider_name: string;
  model_name: string;
  template_key: string;
  audience_name: string;
  timezone: string;
  schedule_cron: string | null;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type NewsletterInput = {
  name: string;
  description: string;
  prompt: string;
  provider_name: string;
  model_name: string;
  template_key: string;
  audience_name: string;
  timezone: string;
  schedule_cron: string;
  status: string;
  notes: string;
};

export const emptyNewsletterInput: NewsletterInput = {
  name: "",
  description: "",
  prompt: "",
  provider_name: "openai",
  model_name: "gpt-4o-mini",
  template_key: "signal",
  audience_name: "default-audience",
  timezone: "UTC",
  schedule_cron: "",
  status: "draft",
  notes: ""
};

export function toNewsletterInput(newsletter: Newsletter): NewsletterInput {
  return {
    name: newsletter.name,
    description: newsletter.description ?? "",
    prompt: newsletter.prompt,
    provider_name: newsletter.provider_name,
    model_name: newsletter.model_name,
    template_key: newsletter.template_key,
    audience_name: newsletter.audience_name,
    timezone: newsletter.timezone,
    schedule_cron: newsletter.schedule_cron ?? "",
    status: newsletter.status,
    notes: newsletter.notes ?? ""
  };
}
