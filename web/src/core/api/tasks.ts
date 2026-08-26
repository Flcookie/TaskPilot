// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import { fetchStream } from "../sse";

import type { EvaluationResult, LLMEvaluation } from "./evaluate";
import { resolveServiceURL } from "./resolve-service-url";
import type { ChatEvent } from "./types";

export interface TaskRecord {
  id: string;
  status: string;
  workflow_type: string;
  thread_id: string;
  selected_skills: string[];
  current_node?: string | null;
  error?: string | null;
}

export interface ProcessMetrics {
  plan_quality: number;
  tool_precision: number;
  recovery_rate: number;
  token_efficiency: number;
  loop_stability: number;
  faithfulness: number;
  skill_hit_rate?: number | null;
  skill_token_delta?: number | null;
  tool_calls: number;
  token_total: number;
  latency_ms?: number | null;
  replan_count: number;
}

export interface SkillLoadingArm {
  mode: string;
  tokens: number;
  skill_count: number;
  selected_skills: string[];
}

export interface SkillLoadingCompare {
  none: SkillLoadingArm;
  all_injected: SkillLoadingArm;
  dynamic: SkillLoadingArm;
  dynamic_saves_tokens: boolean;
}

export interface AgentEvaluationResult extends EvaluationResult {
  process?: ProcessMetrics;
  process_score?: number;
  final_score?: number;
  skill_loading?: SkillLoadingCompare;
}

interface RawTaskEvaluation {
  process?: ProcessMetrics;
  process_score?: number;
  report?: {
    metrics?: EvaluationResult["metrics"];
    score?: number;
    final_score?: number;
    grade?: string;
    llm_evaluation?: LLMEvaluation;
    summary?: string;
  };
  report_score?: number;
  report_grade?: string;
  final_score?: number;
  summary?: string;
  skill_loading?: SkillLoadingCompare;
}

const EMPTY_METRICS: EvaluationResult["metrics"] = {
  word_count: 0,
  citation_count: 0,
  unique_sources: 0,
  image_count: 0,
  section_count: 0,
  section_coverage_score: 0,
  sections_found: [],
  sections_missing: [],
  has_title: false,
  has_key_points: false,
  has_overview: false,
  has_citations_section: false,
};

export async function fetchTask(taskId: string): Promise<TaskRecord> {
  const response = await fetch(resolveServiceURL(`tasks/${taskId}`));
  if (!response.ok) {
    throw new Error(`Failed to fetch task: ${response.statusText}`);
  }
  return response.json();
}

export async function evaluateTask(
  taskId: string,
  options: {
    report?: string;
    query?: string;
    reportStyle?: string;
    useLlm?: boolean;
  } = {},
): Promise<AgentEvaluationResult> {
  const response = await fetch(resolveServiceURL(`tasks/${taskId}/evaluate`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      report: options.report,
      query: options.query,
      report_style: options.reportStyle ?? "default",
      use_llm: options.useLlm ?? false,
    }),
  });
  if (!response.ok) {
    throw new Error(`Task evaluation failed: ${response.statusText}`);
  }
  const raw = (await response.json()) as RawTaskEvaluation;
  const report = raw.report ?? {};
  return {
    metrics: report.metrics ?? EMPTY_METRICS,
    score: report.score ?? report.final_score ?? raw.report_score ?? raw.final_score ?? 0,
    grade: report.grade ?? raw.report_grade ?? "-",
    llm_evaluation: report.llm_evaluation,
    summary: report.summary ?? raw.summary,
    process: raw.process,
    process_score: raw.process_score,
    final_score: raw.final_score,
    skill_loading: raw.skill_loading,
  };
}

export async function* replayTask(
  taskId: string,
  options: { abortSignal?: AbortSignal } = {},
): AsyncIterable<ChatEvent> {
  const stream = fetchStream(resolveServiceURL(`tasks/${taskId}/replay`), {
    body: JSON.stringify({}),
    signal: options.abortSignal,
  });
  for await (const event of stream) {
    if (event.data == null) {
      continue;
    }
    try {
      yield {
        type: event.event,
        data: JSON.parse(event.data),
      } as ChatEvent;
    } catch (error) {
      console.error(error);
    }
  }
}
