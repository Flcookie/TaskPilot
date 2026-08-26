// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import { extractTaskIdFromSearchParams } from "../src/core/replay/get-replay-id";

describe("Task replay search params", () => {
  it("reads task id from ?task=", () => {
    expect(extractTaskIdFromSearchParams("task=abc-123")).toBe("abc-123");
  });

  it("returns null when task is missing", () => {
    expect(extractTaskIdFromSearchParams("replay=demo")).toBeNull();
  });
});
