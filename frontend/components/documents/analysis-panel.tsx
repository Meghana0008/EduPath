"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { AnalysisResult } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AnalysisPanel({ result, title }: { result: AnalysisResult; title: string }) {
  const chartData = Object.entries(result.dimensions).map(([key, value]) => ({
    name: key.replace(/_/g, " "),
    score: value,
  }));

  const colors = ["#348ea3", "#c4922e", "#2d7289", "#b68f5a", "#4fa9bc"];

  return (
    <div className="space-y-6 animate-fade-in">
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4 mb-6">
            <div className="text-center">
              <span className="font-display text-4xl font-bold text-ocean-800">
                {Math.round(result.overall_score)}
              </span>
              <span className="text-sm text-ocean-500 block">Overall Score</span>
            </div>
          </div>

          {chartData.length > 0 && (
            <div className="h-48 mb-6">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} layout="vertical" margin={{ left: 80 }}>
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={75} />
                  <Tooltip />
                  <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                    {chartData.map((_, i) => (
                      <Cell key={i} fill={colors[i % colors.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-medium text-emerald-700 mb-2">Strengths</h4>
              <ul className="space-y-1">
                {result.strengths.map((s, i) => (
                  <li key={i} className="text-sm text-ocean-700 flex gap-2">
                    <span className="text-emerald-500 shrink-0">+</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="text-sm font-medium text-amber-700 mb-2">Improvements</h4>
              <ul className="space-y-1">
                {result.improvements.map((s, i) => (
                  <li key={i} className="text-sm text-ocean-700 flex gap-2">
                    <span className="text-amber-500 shrink-0">→</span>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {result.suggestions.length > 0 && (
            <div className="mt-4 pt-4 border-t border-ocean-100">
              <h4 className="text-sm font-medium text-ocean-800 mb-2">Suggestions</h4>
              <ul className="space-y-1">
                {result.suggestions.map((s, i) => (
                  <li key={i} className="text-sm text-ocean-600">{s}</li>
                ))}
              </ul>
            </div>
          )}

          {result.ai_generated_draft && (
            <div className="mt-4 pt-4 border-t border-ocean-100">
              <h4 className="text-sm font-medium text-ocean-800 mb-2">AI Draft</h4>
              <div className="text-sm text-ocean-700 bg-ocean-50 rounded-xl p-4 whitespace-pre-wrap">
                {result.ai_generated_draft}
              </div>
            </div>
          )}

          <p className="text-xs text-ocean-400 mt-4 italic">{result.disclaimer}</p>
        </CardContent>
      </Card>
    </div>
  );
}
