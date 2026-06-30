"use client";

import { useState } from "react";
import api from "../services/api";
import { downloadPDF } from "../services/pdf";

interface SectionResult {
  score: number;
  matched: string[];
  inferred: string[];
  missing: string[];
}

const METRIC_ORDER: Array<{
  key: "skills" | "experience" | "education" | "certifications" | "projects";
  label: string;
}> = [
  { key: "skills", label: "Skills" },
  { key: "experience", label: "Experience" },
  { key: "education", label: "Education" },
  { key: "certifications", label: "Certifications" },
  { key: "projects", label: "Projects" },
];

function tierFor(score: number) {
  if (score >= 75) {
    return {
      label: "Strong match",
      ring: "#1a7f37",
      chipBg: "#e7f7ec",
      chipBorder: "#bfe6cc",
      chipText: "#1a7f37",
    };
  }
  if (score >= 50) {
    return {
      label: "Needs improvement",
      ring: "#9a6700",
      chipBg: "#fff6db",
      chipBorder: "#f0dd9a",
      chipText: "#9a6700",
    };
  }
  return {
    label: "Weak match",
    ring: "#cf222e",
    chipBg: "#fff0f0",
    chipBorder: "#f5c2c4",
    chipText: "#cf222e",
  };
}

function ScoreRing({ score }: { score: number }) {
  const tier = tierFor(score);
  const radius = 80;
  const stroke = 13;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.min(Math.max(score, 0), 100) / 100);

  return (
    <div className="relative h-[196px] w-[196px] shrink-0">
      <svg width="196" height="196" viewBox="0 0 196 196" className="-rotate-90">
        <circle
          cx="98"
          cy="98"
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={stroke}
        />
        <circle
          cx="98"
          cy="98"
          r={radius}
          fill="none"
          stroke={tier.ring}
          strokeWidth={stroke}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 700ms ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono-data text-[42px] font-bold leading-none text-[#0f172a]">
          {score}
          <span className="text-xl align-top">%</span>
        </span>
        <span className="mt-1.5 text-[11px] uppercase tracking-wide text-[#818b94]">
          ATS score
        </span>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  const tier = tierFor(value);
  return (
    <div className="rounded-xl border border-[#e2e8f0] bg-white p-4 text-center shadow-sm">
      <span className="text-xs font-medium uppercase tracking-wide text-[#818b94]">
        {label}
      </span>
      <div className="font-mono-data mt-1.5 text-2xl font-bold text-[#0f172a]">
        {value}%
      </div>
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-[#f1f5f9]">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${Math.min(Math.max(value, 0), 100)}%`,
            backgroundColor: tier.ring,
          }}
        />
      </div>
    </div>
  );
}

function ChipGroup({
  title,
  items,
  variant,
  emptyLabel,
}: {
  title: string;
  items: string[];
  variant: "good" | "warn" | "bad";
  emptyLabel: string;
}) {
  const styles = {
    good: {
      dot: "bg-[#1a7f37]",
      chip: "bg-[#e7f7ec] border-[#bfe6cc] text-[#1a7f37]",
    },
    warn: {
      dot: "bg-[#9a6700]",
      chip: "bg-[#fff6db] border-[#f0dd9a] text-[#9a6700]",
    },
    bad: {
      dot: "bg-[#cf222e]",
      chip: "bg-[#fff0f0] border-[#f5c2c4] text-[#cf222e]",
    },
  }[variant];

  return (
    <div>
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${styles.dot}`} />
        <h3 className="text-sm font-semibold text-[#0f172a]">{title}</h3>
        <span className="font-mono-data text-xs text-[#818b94]">{items.length}</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.length ? (
          items.map((item, index) => (
            <span
              key={index}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${styles.chip}`}
            >
              {item}
            </span>
          ))
        ) : (
          <span className="text-sm text-[#818b94]">{emptyLabel}</span>
        )}
      </div>
    </div>
  );
}

export default function Home() {
  const [text, setText] = useState("");
  const [jdText, setJdText] = useState("");
  const [loading, setLoading] = useState(false);
  const [fileName, setFileName] = useState("");
  const [overallScore, setOverallScore] = useState(0);
  const [hasRun, setHasRun] = useState(false);

  const [skills, setSkills] = useState<SectionResult | null>(null);
  const [experience, setExperience] = useState<SectionResult | null>(null);
  const [education, setEducation] = useState<SectionResult | null>(null);
  const [certifications, setCertifications] = useState<SectionResult | null>(null);
  const [projects, setProjects] = useState<SectionResult | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const metricValues: Record<string, number> = {
    skills: skills?.score ?? 0,
    experience: experience?.score ?? 0,
    education: education?.score ?? 0,
    certifications: certifications?.score ?? 0,
    projects: projects?.score ?? 0,
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setFileName(file.name);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await api.post("/api/upload", formData);
      setText(response.data.text);
    } catch (error) {
      console.error(error);
      alert("Unable to upload resume.");
    }
  };

  const analyzeResume = async () => {
    if (!text) {
      alert("Upload a resume first.");
      return;
    }
    if (!jdText.trim()) {
      alert("Paste a Job Description first.");
      return;
    }

    try {
      setLoading(true);

      const response = await api.post("/api/analyze", {
        resume_text: text,
        jd_text: jdText,
        resume_name: fileName || "Uploaded Resume",
      });

      if (response.data.error) {
        alert(response.data.error);
        setLoading(false);
        return;
      }

      setOverallScore(response.data.overall_score);
      setSkills(response.data.skills);
      setExperience(response.data.experience);
      setEducation(response.data.education);
      setCertifications(response.data.certifications);
      setProjects(response.data.projects);
      setSuggestions(response.data.suggestions);
      setHasRun(true);
    } catch (error) {
      console.error(error);
      alert("Analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = () => {
    downloadPDF(overallScore, skills, experience, education, certifications, projects, suggestions);
  };

  const tier = tierFor(overallScore);
  const missingMinusInferred =
    skills?.missing?.filter((item) => !skills?.inferred?.includes(item)) ?? [];

  return (
    <div className="min-h-screen bg-[#f8fafc]">
      {/* Top bar */}
      <header className="border-b border-[#e2e8f0] bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#0f172a] font-mono-data text-lg font-bold text-white">
            &gt;_
          </div>
          <div>
            <h1 className="text-2xl font-bold leading-tight text-[#0f172a]">
              ATS Resume Analyzer
            </h1>
            <p className="mt-0.5 text-sm text-[#818b94]">
              Analyze your resume against any job description, with a match score
              for skills, experience, education, and projects.
            </p>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-5 px-6 py-5 lg:grid-cols-[360px_1fr]">
        {/* Left: inputs */}
        <aside className="lg:sticky lg:top-8 lg:self-start">
          <div className="rounded-2xl border border-[#e2e8f0] bg-white p-4 shadow-md">
            <h2 className="text-sm font-semibold text-[#0f172a]">1. Upload resume</h2>
            <label className="mt-3 flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[#cbd5e1] bg-[#f8fafc] px-4 py-5 text-center transition hover:border-[#2563eb] hover:bg-[#eaf1ff]">
              <input
                type="file"
                accept=".pdf"
                onChange={handleUpload}
                className="hidden"
              />
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill="none"
                stroke="#818b94"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M7 18a4.5 4.5 0 0 1-1.07-8.86A5.5 5.5 0 0 1 16.6 7.5 4 4 0 0 1 17 15.5" />
                <path d="M12 12v7" />
                <path d="M9 15l3-3 3 3" />
              </svg>
              <span className="text-sm text-[#4b5560]">
                {fileName ? (
                  <span className="font-mono-data text-[#0f172a]">{fileName}</span>
                ) : (
                  <>
                    <span className="font-medium text-[#2563eb]">Choose a PDF</span>{" "}
                    to upload your resume
                  </>
                )}
              </span>
            </label>
            {fileName && (
              <p className="mt-2 flex items-center gap-1.5 text-xs font-medium text-[#1a7f37]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#1a7f37]" />
                Resume uploaded
              </p>
            )}

            <h2 className="mt-6 text-sm font-semibold text-[#0f172a]">2. Paste job description</h2>
            <textarea
              className="mt-3 h-32 w-full resize-none rounded-lg border border-[#e2e8f0] bg-[#f8fafc] p-3 text-sm text-[#0f172a] outline-none transition focus:border-[#2563eb] focus:bg-white"
              placeholder="Paste the job description here..."
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
            />

            <button
              disabled={!text || !jdText || loading}
              onClick={analyzeResume}
              className="mt-4 h-11 w-full rounded-lg bg-[#2563eb] text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:bg-[#cbd5e1] disabled:text-[#818b94]"
            >
              {loading ? "Analyzing..." : "Analyze resume"}
            </button>

            <button
              onClick={downloadReport}
              disabled={overallScore === 0}
              className="mt-2 h-11 w-full rounded-lg border border-[#e2e8f0] bg-white text-sm font-semibold text-[#0f172a] transition hover:bg-[#f8fafc] disabled:cursor-not-allowed disabled:text-[#818b94]"
            >
              Download report
            </button>
          </div>
        </aside>

        {/* Right: report */}
        <section>
          {!hasRun ? (
            <div className="flex h-full min-h-[300px] flex-col items-center justify-center rounded-xl border border-dashed border-[#e2e8f0] bg-white px-6 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#f8fafc] font-mono-data text-lg text-[#818b94]">
                ?
              </div>
              <h3 className="mt-4 text-base font-semibold text-[#0f172a]">
                No analysis yet
              </h3>
              <p className="mt-1 max-w-sm text-sm text-[#818b94]">
                Upload a resume and paste a job description, then run an analysis to
                see your score breakdown here.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Score hero */}
              <div className="flex flex-col items-center gap-6 rounded-2xl border border-[#e2e8f0] bg-white p-6 shadow-md sm:flex-row sm:items-center">
                <ScoreRing score={overallScore} />
                <div className="flex-1 text-center sm:text-left">
                  <span
                    className="inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold"
                    style={{
                      backgroundColor: tier.chipBg,
                      borderColor: tier.chipBorder,
                      color: tier.chipText,
                    }}
                  >
                    {tier.label}
                  </span>
                  <p className="mt-3 text-sm text-[#4b5560]">
                    Based on skills, experience, education, certifications, and
                    project evidence matched against the job description.
                  </p>
                </div>
              </div>

              {/* Metric breakdown */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {METRIC_ORDER.map((m) => (
                  <MetricCard key={m.key} label={m.label} value={metricValues[m.key]} />
                ))}
              </div>

              {/* Skills detail */}
              <div className="rounded-2xl border border-[#e2e8f0] bg-white p-6 shadow-sm">
                <h2 className="text-sm font-semibold text-[#0f172a]">Skills breakdown</h2>
                <div className="mt-5 grid gap-6 sm:grid-cols-3">
                  <ChipGroup
                    title="Matched"
                    items={skills?.matched ?? []}
                    variant="good"
                    emptyLabel="No matched skills."
                  />
                  <ChipGroup
                    title="Inferred"
                    items={skills?.inferred ?? []}
                    variant="warn"
                    emptyLabel="No inferred skills."
                  />
                  <ChipGroup
                    title="Missing"
                    items={missingMinusInferred}
                    variant="bad"
                    emptyLabel="No missing skills."
                  />
                </div>
              </div>

              {/* Suggestions */}
              <div className="rounded-2xl border border-[#e2e8f0] bg-white p-6 shadow-sm">
                <h2 className="text-sm font-semibold text-[#0f172a]">Suggestions</h2>
                <ul className="mt-4 space-y-2">
                  {suggestions.length ? (
                    suggestions.map((item, index) => (
                      <li
                        key={index}
                        className="flex gap-3 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#4b5560]"
                      >
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="#f59e0b"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          className="mt-0.5 shrink-0"
                          aria-hidden="true"
                        >
                          <path d="M9 18h6" />
                          <path d="M10 22h4" />
                          <path d="M12 2a6 6 0 0 0-3.7 10.7c.6.5 1.2 1.4 1.4 2.3h4.6c.2-.9.8-1.8 1.4-2.3A6 6 0 0 0 12 2Z" />
                        </svg>
                        <span>{item}</span>
                      </li>
                    ))
                  ) : (
                    <li className="text-sm text-[#818b94]">No suggestions.</li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
