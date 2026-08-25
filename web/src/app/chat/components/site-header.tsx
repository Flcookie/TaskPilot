// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import { useTranslations } from 'next-intl';

import { LanguageSwitcher } from "~/components/task-pilot/language-switcher";

export function SiteHeader() {
  const t = useTranslations('header');

  return (
    <header className="supports-backdrop-blur:bg-background/80 bg-background/40 sticky top-0 left-0 z-40 flex h-15 w-full flex-col items-center backdrop-blur-lg">
      <div className="container flex h-15 items-center justify-between px-3">
        <div className="text-xl font-medium">
          <span>{t('title')}</span>
        </div>
        <div className="relative flex items-center gap-2">
          <LanguageSwitcher />
        </div>
      </div>
      <hr className="from-border/0 via-border/70 to-border/0 m-0 h-px w-full border-none bg-gradient-to-r" />
    </header>
  );
}
