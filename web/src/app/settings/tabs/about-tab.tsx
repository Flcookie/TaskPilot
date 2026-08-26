// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import { BadgeInfo } from "lucide-react";
import { useLocale } from "next-intl";

import { Markdown } from "~/components/task-pilot/markdown";

import aboutEn from "./about-en.md";
import aboutZh from "./about-zh.md";
import type { Tab } from "./types";

export const AboutTab: Tab = () => {
  const locale = useLocale();
  const aboutContent = locale === "zh" ? aboutZh : aboutEn;

  return <Markdown>{aboutContent}</Markdown>;
};
AboutTab.icon = BadgeInfo;
AboutTab.displayName = "About";
