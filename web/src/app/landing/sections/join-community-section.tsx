// Copyright (c) 2025 TaskPilot contributors
// SPDX-License-Identifier: MIT

import { useTranslations } from "next-intl";

import { AuroraText } from "~/components/magicui/aurora-text";

import { SectionHeader } from "../components/section-header";

export function JoinCommunitySection() {
  const t = useTranslations("landing.joinCommunity");
  return (
    <section className="flex w-full flex-col items-center justify-center pb-12">
      <SectionHeader
        anchor="join-community"
        title={
          <AuroraText colors={["#60A5FA", "#A5FA60", "#A560FA"]}>
            {t("title")}
          </AuroraText>
        }
        description={t("description")}
      />
    </section>
  );
}
