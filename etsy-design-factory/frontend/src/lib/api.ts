export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type ApprovalAction =
  | "APPROVE"
  | "REJECT"
  | "MORE_ORIGINAL"
  | "CLOSER_TO_COLLECTION"
  | "CHANGE_COMPOSITION"
  | "CHANGE_PALETTE"
  | "MORE_TEXTURE"
  | "LESS_TEXTURE"
  | "MORE_MINIMAL"
  | "MORE_DETAILED"
  | "CREATE_VARIATIONS";

export interface DashboardSummary {
  plan_date: string;
  target_final_designs: number | null;
  generated: number;
  qc_passed: number;
  repairing: number;
  awaiting_approval: number;
  approved: number;
  rejected: number;
  today_cost_usd: number;
  cost_per_approved_design_usd: number | null;
}

export interface ScoreSummary {
  value: number;
  confidence: number;
  reasoning: string;
  problems: string[];
}

export interface CandidateSummary {
  id: string;
  concept_id: string;
  design_genome_id: string;
  collection_id: string | null;
  collection_name: string | null;
  status: string;
  image_url: string;
  width_px: number;
  height_px: number;
  is_repair: boolean;
  created_at: string;
  scores: Record<string, ScoreSummary> | null;
  subject: string | null;
  style: string | null;
  palette: string | null;
}

export interface CandidateListResponse {
  items: CandidateSummary[];
  total: number;
}

export interface ApprovalResult {
  candidate_id: string;
  action: string;
  artwork_id: string | null;
  new_concept_id: string | null;
}

export interface BulkApprovalResponse {
  results: ApprovalResult[];
}

export interface ProductionPlanResponse {
  id: string;
  plan_date: string;
  target_final_designs: number;
  portfolio_allocation: Record<string, number>;
  production_slots: number;
  experimental_slots: number;
  winner_mutation_slots: number;
  budget_cap_usd: number;
  rationale: string;
}

export interface MarketSignalOut {
  id: string;
  category: string;
  description: string;
  confidence: number;
  source: string;
  created_at: string;
}

export interface MarketSignalListResponse {
  items: MarketSignalOut[];
}

export interface ResearchQueryOut {
  query: string;
  category: string;
  reason: string;
}

export interface ResearchPlanResponse {
  plan_date: string;
  queries: ResearchQueryOut[];
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON -- fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function imageUrl(candidateId: string): string {
  return `${API_BASE}/api/candidates/${candidateId}/image`;
}

export function getDashboard(planDate?: string): Promise<DashboardSummary> {
  const q = planDate ? `?plan_date=${encodeURIComponent(planDate)}` : "";
  return request<DashboardSummary>(`/api/dashboard/today${q}`);
}

export function listCandidates(params: {
  status?: string;
  collectionId?: string;
  limit?: number;
  offset?: number;
}): Promise<CandidateListResponse> {
  const search = new URLSearchParams();
  if (params.status) search.set("status", params.status);
  if (params.collectionId) search.set("collection_id", params.collectionId);
  search.set("limit", String(params.limit ?? 60));
  search.set("offset", String(params.offset ?? 0));
  return request<CandidateListResponse>(`/api/candidates?${search.toString()}`);
}

export function applyApproval(
  candidateId: string,
  body: { action: ApprovalAction; actor: string; notes?: string }
): Promise<ApprovalResult> {
  return request<ApprovalResult>(`/api/candidates/${candidateId}/approval`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function applyBulkApproval(body: {
  candidate_ids: string[];
  action: ApprovalAction;
  actor: string;
}): Promise<BulkApprovalResponse> {
  return request<BulkApprovalResponse>(`/api/candidates/bulk-approval`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function triggerProductionPlan(body: {
  plan_date: string;
  target_final_designs?: number;
}): Promise<ProductionPlanResponse> {
  return request<ProductionPlanResponse>(`/api/production/plan`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getProductionPlan(planDate: string): Promise<ProductionPlanResponse> {
  return request<ProductionPlanResponse>(`/api/production/plan/${planDate}`);
}

export function listMarketSignals(withinDays = 7): Promise<MarketSignalListResponse> {
  return request<MarketSignalListResponse>(`/api/market-intelligence/signals?within_days=${withinDays}`);
}

export function getResearchQueries(): Promise<ResearchPlanResponse> {
  return request<ResearchPlanResponse>(`/api/market-intelligence/research-queries`);
}

export { ApiError };
