// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import { useEffect, useRef, useState } from "react";

import { env } from "~/env";

import type { TaskPilotConfig } from "../config";
import { useReplay } from "../replay";

import { fetchReplayTitle } from "./chat";
import { resolveServiceURL } from "./resolve-service-url";

export function useReplayMetadata() {
  const { isReplay, taskId } = useReplay();
  const [title, setTitle] = useState<string | null>(null);
  const isLoading = useRef(false);
  const [error, setError] = useState<boolean>(false);
  useEffect(() => {
    if (!isReplay) {
      return;
    }
    if (taskId) {
      setTitle(`Task ${taskId.slice(0, 8)}`);
      document.title = `Task replay - TaskPilot`;
      return;
    }
    if (title || isLoading.current) {
      return;
    }
    isLoading.current = true;
    fetchReplayTitle()
      .then((title) => {
        setError(false);
        setTitle(title ?? null);
        if (title) {
          document.title = `${title} - TaskPilot`;
        }
      })
      .catch(() => {
        setError(true);
        setTitle("Error: the replay is not available.");
        document.title = "TaskPilot";
      })
      .finally(() => {
        isLoading.current = false;
      });
  }, [isLoading, isReplay, taskId, title]);
  return { title, isLoading, hasError: error };
}

const DEFAULT_CONFIG: TaskPilotConfig = {
  rag: { provider: "" },
  models: { basic: [], reasoning: [] },
};

export function useConfig(): {
  config: TaskPilotConfig;
  loading: boolean;
} {
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<TaskPilotConfig>(DEFAULT_CONFIG);

  useEffect(() => {
    if (env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY) {
      setLoading(false);
      return;
    }

    const fetchConfigWithRetry = async () => {
      const maxRetries = 2;
      let lastError: Error | null = null;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          const res = await fetch(resolveServiceURL("./config"), {
            signal: AbortSignal.timeout(5000), // 5 second timeout
          });

          if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
          }

          const configData = await res.json();
          setConfig(configData);
          setLoading(false);
          return; // Success, exit retry loop
        } catch (err) {
          lastError = err instanceof Error ? err : new Error(String(err));

          // Log attempt details
          if (attempt === 0) {
            const apiUrl = resolveServiceURL("./config");
            console.warn(
              `[Config] Failed to fetch from ${apiUrl}: ${lastError.message}`,
            );
          }

          // Wait before retrying (exponential backoff: 100ms, 500ms)
          if (attempt < maxRetries) {
            const delay = Math.pow(2, attempt) * 100;
            await new Promise((resolve) => setTimeout(resolve, delay));
          }
        }
      }

      // All retries failed, use default config
      console.warn(
        `[Config] Using default config after ${maxRetries + 1} attempts. Last error: ${lastError?.message ?? "Unknown"}`,
      );
      setConfig(DEFAULT_CONFIG);
      setLoading(false);
    };

    void fetchConfigWithRetry();
  }, []);

  return { config, loading };
}
