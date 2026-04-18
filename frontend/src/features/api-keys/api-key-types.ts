export type { ProviderTypeOption } from "../providers/provider-types";

export type ApiKeySummary = {
  id: number;
  name: string;
  provider_type: string;
  masked_key: string;
  is_active: boolean;
  auth_type: string;
  oauth_plan_type: string | null;
  oauth_account_id: string | null;
  oauth_expires_at: string | null;
  last_used_at: string | null;
  created_at: string;
  updated_at: string;
  from_email: string | null;
};

export type ApiKeyDetail = ApiKeySummary;

export type ApiKeyInput = {
  name: string;
  provider_type: string;
  key_value: string | null;
  is_active: boolean;
  from_email: string | null;
};

export const emptyApiKeyInput: ApiKeyInput = {
  name: "",
  provider_type: "",
  key_value: "",
  is_active: true,
  from_email: null
};

export function toApiKeyInput(detail: ApiKeyDetail): ApiKeyInput {
  return {
    name: detail.name,
    provider_type: detail.provider_type,
    key_value: "",
    is_active: detail.is_active,
    from_email: detail.from_email
  };
}
