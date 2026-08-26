// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import { useSearchParams } from "next/navigation";
import { useMemo } from "react";

import { env } from "~/env";

import { extractReplayIdFromSearchParams, extractTaskIdFromSearchParams } from "./get-replay-id";

export function useReplay() {
  const searchParams = useSearchParams();
  const replayId = useMemo(
    () => extractReplayIdFromSearchParams(searchParams.toString()),
    [searchParams],
  );
  const taskId = useMemo(
    () => extractTaskIdFromSearchParams(searchParams.toString()),
    [searchParams],
  );
  return {
    isReplay:
      replayId != null ||
      taskId != null ||
      env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY,
    replayId,
    taskId,
  };
}
