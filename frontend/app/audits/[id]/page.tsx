import { Suspense } from "react";
import { AuditReportView } from "@/components/report";

// The audit id is only known at request time, so the client component that reads
// it (via useParams) sits inside Suspense, as cacheComponents requires.
export default function AuditPage() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-12 sm:py-16">
      <Suspense fallback={<p className="text-neutral-500">Loading audit…</p>}>
        <AuditReportView />
      </Suspense>
    </main>
  );
}
