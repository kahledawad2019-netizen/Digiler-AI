"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { llmApi, studentApi } from "@/lib/client";

const STYLES = ["concise", "balanced", "detailed", "example-driven"];
const LEVELS = ["beginner", "intermediate", "advanced"];
const PACES = ["slow", "normal", "fast"];

function Choice({ label, options, value, onChange }: {
  label: string; options: string[]; value: string; onChange: (v: string) => void;
}) {
  return (
    <div>
      <p className="mb-1.5 text-sm font-medium">{label}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <button key={o} onClick={() => onChange(o)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
              value === o ? "border-primary bg-accent text-accent-foreground" : "hover:bg-accent"
            }`}>
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function SettingsPage() {
  const [style, setStyle] = useState("balanced");
  const [level, setLevel] = useState("intermediate");
  const [pace, setPace] = useState("normal");
  const [lang, setLang] = useState("en");
  const llm = useQuery({ queryKey: ["llm"], queryFn: llmApi.status });
  const save = useMutation({
    mutationFn: () => studentApi.preferences({
      explanation_style: style, level, learning_pace: pace, preferred_language: lang,
    }),
  });

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl space-y-5 p-6">
        <h1 className="text-xl font-semibold">Settings</h1>

        <Card>
          <CardHeader><CardTitle>Learning preferences</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <Choice label="Explanation style" options={STYLES} value={style} onChange={setStyle} />
            <Choice label="Learning level" options={LEVELS} value={level} onChange={setLevel} />
            <Choice label="Learning pace" options={PACES} value={pace} onChange={setPace} />
            <Choice label="Preferred language" options={["en", "ar"]} value={lang} onChange={setLang} />
            <Button onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : save.isSuccess ? <Check className="h-4 w-4" /> : null}
              Save preferences
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Language model</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Provider</span>
              <span className="font-medium">{llm.data?.provider ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Model</span>
              <span className="font-medium">{llm.data?.model ?? "—"}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Status</span>
              <Badge variant={llm.data?.reachable ? "success" : "warning"}>
                {llm.data?.reachable ? "Connected" : "Offline (extractive fallback)"}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
