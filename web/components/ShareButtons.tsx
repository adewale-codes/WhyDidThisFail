"use client";

import CopyButton from "./CopyButton";

export default function ShareButtons({
  shareUrl,
  format,
  cause,
}: {
  shareUrl: string;
  format: string;
  cause: string;
}) {
  const slackText = `*WhyDidThisFail?* diagnosis — _${format} failure_\n>${cause}\n${shareUrl}`;
  const githubText = `**WhyDidThisFail?** diagnosis — _${format} failure_\n\n> ${cause}\n\n[View full diagnosis](${shareUrl})`;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <CopyButton text={shareUrl} label="Copy link" copiedLabel="Link copied" />
      <CopyButton text={slackText} label="Copy for Slack" copiedLabel="Copied" />
      <CopyButton text={githubText} label="Copy as GitHub markdown" copiedLabel="Copied" />
    </div>
  );
}
