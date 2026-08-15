import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatClock(seconds?: number | null): string {
  if (seconds == null) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function initials(name?: string, email?: string): string {
  const base = (name || email || "?").trim();
  const parts = base.split(/[\s@.]+/).filter(Boolean);
  return (parts[0]?.[0] ?? "?").toUpperCase() + (parts[1]?.[0]?.toUpperCase() ?? "");
}

// -- display formatting: slugs -> professional Title Case ------------------- //
const ACRONYMS = new Set([
  "ai", "ml", "dl", "nlp", "sql", "rag", "api", "eda", "llm", "knn", "tv",
  "ocr", "rl", "cnn", "rnn", "svm", "pca", "db", "id", "ui", "ux", "csv",
]);

/** Turn a slug ("applied-dl", "w02-s1", "db-reference-book") into a readable
 *  Title-Case label. Recognises week/session codes and common acronyms. */
export function formatTitle(slug?: string | null): string {
  if (!slug) return "";
  return slug
    .replace(/[._-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .map((w) => {
      const lw = w.toLowerCase();
      if (ACRONYMS.has(lw)) return lw.toUpperCase();
      const wk = lw.match(/^w(\d{1,2})$/);
      if (wk) return `Week ${parseInt(wk[1], 10)}`;
      const ss = lw.match(/^s(\d{1,2})$/);
      if (ss) return `Session ${parseInt(ss[1], 10)}`;
      return w.charAt(0).toUpperCase() + w.slice(1);
    })
    .join(" ");
}

// Confident labels for the known courses (inferred from their materials).
const COURSE_LABELS: Record<string, string> = {
  "agentic-ai": "Agentic AI",
  "aiml": "AI & Machine Learning",
  "applied-dl": "Applied Deep Learning",
  "applied-stats": "Applied Statistics",
  "dmv": "Data Mining & Visualization",
  "eng": "English",
  "excel-ai": "Excel & AI",
};

/** Professional course name for a course slug (falls back to formatTitle). */
export function formatCourse(slug?: string | null): string {
  if (!slug) return "";
  return COURSE_LABELS[slug.toLowerCase()] ?? formatTitle(slug);
}
