"use client";

import { CheckCircle2, FileUp, Loader2, RefreshCw, X } from "lucide-react";
import * as React from "react";

interface JournalImportProps {
  apiBaseUrl: string;
}

export function JournalImport({ apiBaseUrl }: JournalImportProps) {
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<{
    imported: number;
    skipped: number;
    total_after: number;
  } | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [replace, setReplace] = React.useState(false);

  const fileRef = React.useRef<HTMLInputElement>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const entries = Array.isArray(parsed) ? parsed : parsed?.entries;
      if (!Array.isArray(entries)) {
        throw new Error("File must be a JSON array of journal entries.");
      }
      const res = await fetch(`${apiBaseUrl}/api/journal/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entries, replace }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setResult({
        imported: data.imported,
        skipped: data.skipped,
        total_after: data.total_after,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-9 items-center gap-2 rounded-lg border border-blue/60 bg-blue/15 px-3 text-xs font-bold text-blue-bright transition-colors hover:bg-blue/25"
      >
        <FileUp className="h-3.5 w-3.5" />
        Import from Streamlit
      </button>

      {open && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-2xl border border-border bg-surface p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-blue-bright">
                  Journal import
                </div>
                <h2 className="mt-1 font-[family-name:var(--font-space-grotesk)] text-xl font-extrabold text-text">
                  Upload signal_journal.json
                </h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  setResult(null);
                  setError(null);
                }}
                aria-label="Close"
                className="grid h-8 w-8 place-items-center rounded-lg border border-border bg-surface-2 text-muted hover:text-text"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <p className="mt-3 text-sm leading-relaxed text-muted">
              Pull <code className="rounded bg-surface-2/60 px-1.5 py-0.5 font-mono text-[0.7rem] text-text">data/signal_journal.json</code> off the Streamlit service and drop it
              here. Entries are upserted by <code className="rounded bg-surface-2/60 px-1.5 py-0.5 font-mono text-[0.7rem] text-text">journal_id</code>, so re-uploading
              the same file is safe.
            </p>

            <label className="mt-4 inline-flex items-center gap-2 text-xs text-muted">
              <input
                type="checkbox"
                checked={replace}
                onChange={(e) => setReplace(e.target.checked)}
                className="h-3.5 w-3.5"
              />
              Replace everything (wipe + write — use only on first import)
            </label>

            <div className="mt-5 grid gap-3">
              <input
                ref={fileRef}
                type="file"
                accept="application/json,.json"
                hidden
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleFile(f);
                }}
              />
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={busy}
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-blue/60 bg-blue/15 px-4 text-sm font-bold text-blue-bright transition-colors hover:bg-blue/25 disabled:opacity-50"
              >
                {busy ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Uploading…
                  </>
                ) : (
                  <>
                    <FileUp className="h-4 w-4" />
                    Choose JSON file
                  </>
                )}
              </button>

              {result && (
                <div className="rounded-xl border border-green/40 bg-green/[0.06] p-4 text-sm">
                  <div className="flex items-center gap-2 text-green-bright">
                    <CheckCircle2 className="h-4 w-4" />
                    <span className="font-bold">Imported</span>
                  </div>
                  <ul className="mt-2 space-y-1 font-mono text-xs text-text">
                    <li>imported: {result.imported}</li>
                    <li>skipped: {result.skipped}</li>
                    <li>total now on disk: {result.total_after}</li>
                  </ul>
                  <button
                    type="button"
                    onClick={() => {
                      window.location.reload();
                    }}
                    className="mt-3 inline-flex items-center gap-1.5 text-xs font-bold text-blue-bright hover:underline"
                  >
                    <RefreshCw className="h-3 w-3" />
                    Reload to view entries
                  </button>
                </div>
              )}
              {error && (
                <div className="rounded-xl border border-red/40 bg-red/[0.05] p-3 text-xs text-red-bright">
                  <div className="font-bold">Import failed</div>
                  <div className="mt-1 font-mono text-[0.7rem] text-muted">{error}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
