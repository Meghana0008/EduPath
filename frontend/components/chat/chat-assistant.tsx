"use client";

import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function ChatAssistant({ opportunityId }: { opportunityId?: string }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);
    try {
      const res = await api.chat(userMsg, opportunityId);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: err instanceof Error ? err.message : "Something went wrong." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={cn(
          "fixed bottom-6 right-6 z-40 flex items-center gap-2 px-5 py-3 rounded-2xl",
          "bg-gradient-to-r from-ocean-700 to-ocean-800 text-white shadow-lg shadow-ocean-900/25",
          "hover:shadow-xl hover:shadow-ocean-900/30 hover:-translate-y-0.5 transition-all duration-300"
        )}
      >
        <Sparkles className="w-5 h-5" />
        <span className="font-medium text-sm hidden sm:inline">Ask EduPath</span>
        <MessageCircle className="w-5 h-5 sm:hidden" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40 bg-ocean-950/20 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <div className="fixed bottom-0 sm:bottom-6 right-0 sm:right-6 z-50 w-full sm:w-[420px] h-[70vh] sm:h-[560px] flex flex-col rounded-t-2xl sm:rounded-2xl border border-ocean-100 bg-white/95 backdrop-blur-xl shadow-2xl animate-slide-up">
            <div className="flex items-center justify-between px-5 py-4 border-b border-ocean-100 bg-gradient-to-r from-ocean-50 to-sand-50 rounded-t-2xl">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-ocean-700 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-white" />
                </div>
                <div>
                  <h3 className="font-display font-semibold text-ocean-900">EduPath Assistant</h3>
                  <p className="text-[10px] text-ocean-500 uppercase tracking-wider">AI Scholar Guide</p>
                </div>
              </div>
              <button onClick={() => setOpen(false)} className="p-1.5 hover:bg-ocean-100 rounded-lg">
                <X className="w-5 h-5 text-ocean-600" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && (
                <div className="text-center py-8 px-4">
                  <p className="text-sm text-ocean-600">
                    Ask about scholarships, deadlines, application tips, or your career path.
                  </p>
                </div>
              )}
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
                    m.role === "user"
                      ? "ml-auto bg-ocean-700 text-white rounded-br-md"
                      : "mr-auto bg-ocean-50 text-ocean-900 border border-ocean-100 rounded-bl-md"
                  )}
                >
                  {m.content}
                </div>
              ))}
              {loading && (
                <div className="mr-auto bg-ocean-50 rounded-2xl px-4 py-3 border border-ocean-100">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 rounded-full bg-ocean-400 animate-pulse-soft" />
                    <span className="w-2 h-2 rounded-full bg-ocean-400 animate-pulse-soft [animation-delay:0.2s]" />
                    <span className="w-2 h-2 rounded-full bg-ocean-400 animate-pulse-soft [animation-delay:0.4s]" />
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            <div className="p-4 border-t border-ocean-100">
              <div className="flex gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                  placeholder="Ask anything..."
                  className="min-h-[44px] max-h-24 resize-none"
                  rows={1}
                />
                <Button onClick={send} disabled={loading || !input.trim()} size="md" className="shrink-0">
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}
