"use client";

import { useState, useRef, useEffect } from "react";

interface CitationExportProps {
  title: string;
  paperId: string;
  source: string;
  createdAt: string;
  category?: string | null;
}

function generateBibTeX(props: CitationExportProps): string {
  const year = new Date(props.createdAt).getFullYear();
  const key = `ari_${props.paperId.replace(/[^a-zA-Z0-9]/g, "_")}_${year}`;
  return `@article{${key},
  title = {${props.title}},
  author = {{Autonomous Research Infrastructure}},
  year = {${year}},
  journal = {ARI Working Papers},
  howpublished = {Autonomous Research Infrastructure for AI Governance},
  note = {Autonomously generated and reviewed via 5-layer pipeline${props.category ? `; category: ${props.category}` : ""}},
  url = {${typeof window !== "undefined" ? window.location.href : ""}},
  urldate = {${new Date().toISOString().slice(0, 10)}}
}`;
}

function generateAPA(props: CitationExportProps): string {
  const date = new Date(props.createdAt);
  const year = date.getFullYear();
  return `Autonomous Research Infrastructure. (${year}). ${props.title}. ARI Working Papers. ${typeof window !== "undefined" ? window.location.href : ""}`;
}

function generatePlainText(props: CitationExportProps): string {
  const year = new Date(props.createdAt).getFullYear();
  return `"${props.title}" — Autonomous Research Infrastructure, ${year}. ${typeof window !== "undefined" ? window.location.href : ""}`;
}

export function CitationExport(props: CitationExportProps) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleEscape);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  async function copyToClipboard(text: string, format: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(format);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(format);
      setTimeout(() => setCopied(null), 2000);
    }
  }

  function downloadBibFile() {
    const bibtex = generateBibTeX(props);
    const blob = new Blob([bibtex], { type: "application/x-bibtex" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ari_${props.paperId}.bib`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const formats = [
    { key: "bibtex", label: "BibTeX", generate: generateBibTeX },
    { key: "apa", label: "APA", generate: generateAPA },
    { key: "plain", label: "Plain Text", generate: generatePlainText },
  ] as const;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1.5 rounded-md bg-primary text-primary-foreground px-3.5 py-1.5 text-xs font-semibold shadow-sm hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        aria-expanded={open}
        aria-haspopup="true"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 2H14l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z"/><path d="M14 2v6h6"/><path d="M9 15h6"/><path d="M9 11h6"/></svg>
        Cite this paper
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1 z-50 w-[calc(100vw-2rem)] sm:w-80 max-w-sm rounded-lg border bg-popover p-3 shadow-lg text-popover-foreground">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-medium">Export citation</p>
            <button
              type="button"
              onClick={downloadBibFile}
              className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Download .bib
            </button>
          </div>
          <div className="space-y-2">
            {formats.map((fmt) => {
              const text = fmt.generate(props);
              return (
                <div key={fmt.key} className="rounded-md border bg-muted/30 p-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {fmt.label}
                    </span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(text, fmt.key)}
                      className="text-[11px] text-primary hover:underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded"
                    >
                      {copied === fmt.key ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap break-all max-h-24 overflow-y-auto font-mono leading-relaxed">
                    {text}
                  </pre>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
