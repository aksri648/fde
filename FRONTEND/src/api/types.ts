export type SessionState = 
  | "DISCOVERING" | "AWAITING_ANSWERS" | "AWAITING_APPROVAL"
  | "HANDOFF_QUEUED" | "HANDOFF_FAILED" | "HANDED_OFF"
  | "FAILED" | "CANCELLED";

export type ApprovalAction = "approve" | "request_changes" | "cancel";

export type AnswerType = "text" | "single_select" | "multi_select" | "number" | "boolean";

export type Route = "APPDEVELOPER" | "LLMDEPLOYER" | "AMBIGUOUS";

export interface SessionSnapshot {
  id: string;
  state: SessionState;
  plan_version: number;
  route: string | null;
  created_at: string;
  updated_at: string;
}

export interface FollowUpQuestionOption {
  label: string;
  value: string;
}

export interface FollowUpQuestion {
  id: string;
  question: string;
  why_it_matters: string;
  required: boolean;
  answer_type: AnswerType;
  options: FollowUpQuestionOption[];
}

export interface DocumentationCitation {
  id: string;
  title: string;
  url: string;
}

export interface ArchitectureProposal {
  title: string;
  business_problem: string;
  business_context: string;
  success_metrics: string[];
  users: string;
  recommended_solution_type: string;
  alternatives: any[];
  architecture_components: any[];
  data_and_integration_plan: string;
  security_and_compliance: string;
  human_in_the_loop_design: string;
  delivery_phases: any[];
  estimated_complexity: string;
  assumptions: string[];
  risks: string[];
  open_questions: string[];
  recommended_route: Route;
  route_rationale: string;
  citation_ids: string[];
}

export interface ProposalResponse {
  proposal: ArchitectureProposal;
  plan_version: number;
  content_hash: string;
  citations: DocumentationCitation[];
}

export interface HandoffStatus {
  outbox_status?: string;
  attempt_count?: number;
  last_error?: string | null;
  session_id: string;
  receipt?: {
    route: string;
    downstream_id: string;
    downstream_status: string;
    accepted_at: string | null;
    attempt_count: number;
  };
}

export interface ErrorResponse {
  error_code: string;
  message: string;
  correlation_id?: string;
}

export interface WebSocketEvent {
  sequence: number;
  event: string;
  timestamp?: string;
  data: Record<string, unknown>;
}
