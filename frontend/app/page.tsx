import { AuditForm } from "@/components/audit-form";
import { AuditHistory } from "@/components/audit-history";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-3xl space-y-12 px-4 py-12 sm:py-16">
      <header className="space-y-3">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">AEO Page Auditor</h1>
        <p className="text-neutral-600 dark:text-neutral-400">
          Paste a URL to see how likely the page is to be picked up and cited by AI answer engines like
          ChatGPT, Perplexity and Google AI Overviews, and what to fix first.
        </p>
      </header>

      <AuditForm />

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Recent audits</h2>
        <AuditHistory />
      </section>
    </main>
  );
}
