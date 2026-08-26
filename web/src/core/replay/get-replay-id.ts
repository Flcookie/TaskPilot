// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

export function extractReplayIdFromSearchParams(params: string) {
  const urlParams = new URLSearchParams(params);
  if (urlParams.has("replay")) {
    return urlParams.get("replay");
  }
  return null;
}

export function extractTaskIdFromSearchParams(params: string) {
  const urlParams = new URLSearchParams(params);
  return urlParams.get("task");
}
