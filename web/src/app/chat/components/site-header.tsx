// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import { useTranslations } from "next-intl";

import { LanguageSwitcher } from "~/components/task-pilot/language-switcher";
import { useStore } from "~/core/store";

export function SiteHeader() {
  const t = useTranslations("header");
  const selectedSkills = useStore((state) => state.selectedSkills);
  const tokenTotal = useStore((state) => state.tokenTotal);

  return (
    <header className="supports-backdrop-blur:bg-background/80 bg-background/40 sticky top-0 left-0 z-40 flex h-15 w-full flex-col items-center backdrop-blur-lg">
      <div className="container flex h-15 items-center justify-between px-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-xl font-medium">{t("title")}</span>
          {selectedSkills.length > 0 && (
            <span className="text-muted-foreground truncate text-xs font-normal">
              {t("skill")}: {selectedSkills.join(", ")}
            </span>
          )}
          {tokenTotal > 0 && (
            <span className="text-muted-foreground shrink-0 text-xs font-normal">
              {t("tokens")}: {tokenTotal.toLocaleString()}
            </span>
          )}
        </div>
        <div className="relative flex items-center gap-2">
          <LanguageSwitcher />
        </div>
      </div>
      <hr className="from-border/0 via-border/70 to-border/0 m-0 h-px w-full border-none bg-gradient-to-r" />
    </header>
  );
}
