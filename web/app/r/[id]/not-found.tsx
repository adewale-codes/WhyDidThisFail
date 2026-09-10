import Link from "next/link";

export default function ResultNotFound() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-4 py-24 text-center">
      <p className="text-sm font-semibold text-muted">404</p>
      <h1 className="mt-2 text-2xl font-bold text-foreground">
        This diagnosis doesn&apos;t exist
      </h1>
      <p className="mt-2 max-w-md text-sm text-muted">
        The link may be mistyped, or the result may have expired. You can run a new diagnosis
        instead.
      </p>
      <Link
        href="/"
        className="mt-6 rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-hover"
      >
        Diagnose a failure
      </Link>
    </main>
  );
}
