// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import type { Citation, Option } from "../messages";

// Tool Calls

export interface ToolCall {
  type: "tool_call";
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ToolCallChunk {
  type: "tool_call_chunk";
  index: number;
  id: string;
  name: string;
  args: string;
}

// Events

interface GenericEvent<T extends string, D extends object> {
  type: T;
  data: {
    id: string;
    thread_id: string;
    agent: "coordinator" | "planner" | "researcher" | "coder" | "reporter";
    role: "user" | "assistant" | "tool";
    finish_reason?: "stop" | "tool_calls" | "interrupt";
  } & D;
}

export interface MessageChunkEvent
  extends GenericEvent<
    "message_chunk",
    {
      content?: string;
      reasoning_content?: string;
    }
  > {}

export interface ToolCallsEvent
  extends GenericEvent<
    "tool_calls",
    {
      tool_calls: ToolCall[];
      tool_call_chunks: ToolCallChunk[];
    }
  > {}

export interface ToolCallChunksEvent
  extends GenericEvent<
    "tool_call_chunks",
    {
      tool_call_chunks: ToolCallChunk[];
    }
  > {}

export interface ToolCallResultEvent
  extends GenericEvent<
    "tool_call_result",
    {
      tool_call_id: string;
      content?: string;
    }
  > {}

export interface InterruptEvent
  extends GenericEvent<
    "interrupt",
    {
      options: Option[];
    }
  > {}

export interface CitationsEvent {
  type: "citations";
  data: {
    thread_id: string;
    citations: Citation[];
  };
}

export interface ErrorEvent {
  type: "error";
  data: {
    thread_id: string;
    error: string;
    reason?: "cancelled" | string;
  };
}

export interface TaskLifecycleEvent {
  type: "task";
  data: {
    task_id: string;
    thread_id: string;
    status?: string;
  };
}

export interface SkillSelectedEvent {
  type: "skill_selected" | "skill_loaded";
  data: {
    selected_skills?: string[];
    skill?: string;
    reason?: string;
    allowed_tools?: string[];
  };
}

export interface TokenUsageEvent {
  type: "token_usage";
  data: {
    prompt_tokens?: number | null;
    completion_tokens?: number | null;
    total_tokens?: number | null;
    estimated?: boolean;
    node?: string | null;
  };
}

export type ChatEvent =
  | MessageChunkEvent
  | ToolCallsEvent
  | ToolCallChunksEvent
  | ToolCallResultEvent
  | InterruptEvent
  | CitationsEvent
  | ErrorEvent
  | TaskLifecycleEvent
  | SkillSelectedEvent
  | TokenUsageEvent;
