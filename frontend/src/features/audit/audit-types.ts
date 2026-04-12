export type AuditEvent = {
  id: number;
  actor_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  payload_json: string | null;
  created_at: string;
};

export type AuditEventListResponse = {
  items: AuditEvent[];
};

export type AuditEventListParams = {
  action?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
};

export type OperationalEvent = {
  id: string;
  source: string;
  source_id: number;
  run_id: number;
  newsletter_id: number;
  newsletter_name: string | null;
  newsletter_slug: string | null;
  event_type: string;
  status: string;
  message: string;
  related_entity: string;
  trigger_mode: string | null;
  recipient_count: number | null;
  provider_id: string | null;
  created_at: string;
};

export type OperationalEventListResponse = {
  items: OperationalEvent[];
};

export type OperationalEventListParams = {
  event_type?: string;
  status?: string;
  search?: string;
  date_from?: string;
  date_to?: string;
};
