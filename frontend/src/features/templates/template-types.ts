export type EmailTemplateSummary = {
  id: number;
  name: string;
  key: string;
  description: string | null;
  is_default: boolean;
  is_system: boolean;
  created_at: string;
  updated_at: string;
};

export type EmailTemplateDetail = EmailTemplateSummary & {
  html_template: string;
};

export type EmailTemplateInput = {
  name: string;
  key: string;
  description: string;
  html_template: string;
  is_default: boolean;
};

export const emptyEmailTemplateInput: EmailTemplateInput = {
  name: "",
  key: "",
  description: "",
  html_template: "",
  is_default: false
};

export function toEmailTemplateInput(detail: EmailTemplateDetail): EmailTemplateInput {
  return {
    name: detail.name,
    key: detail.key,
    description: detail.description ?? "",
    html_template: detail.html_template,
    is_default: detail.is_default
  };
}
