import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getResult } from "@/lib/store";
import { getBaseUrl } from "@/lib/site";
import ResultView from "@/components/ResultView";

type Params = { params: Promise<{ id: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const record = await getResult(id);

  if (!record) {
    return { title: "Diagnosis not found — WhyDidThisFail?" };
  }

  const { result } = record;
  const title = `${result.detected_format} failure: ${truncate(result.cause, 70)}`;
  const description = truncate(result.explanation, 160);

  return {
    title: `${title} — WhyDidThisFail?`,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { card: "summary_large_image", title, description },
  };
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export default async function ResultPage({ params }: Params) {
  const { id } = await params;
  const record = await getResult(id);

  if (!record) {
    notFound();
  }

  const baseUrl = await getBaseUrl();
  const shareUrl = `${baseUrl}/r/${record.id}`;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-12">
      <ResultView record={record} shareUrl={shareUrl} />
    </main>
  );
}
