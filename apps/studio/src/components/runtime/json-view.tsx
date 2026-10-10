import { useState } from "react";
import { Button } from "@/components/ui/button";

export function JsonView({
  value,
  label = "JSON",
}: {
  value: unknown;
  label?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copyStatus, setCopyStatus] = useState("Copy JSON");
  const text = JSON.stringify(value ?? null, null, 2);
  const truncated = text.length > 12000 && !expanded;
  return (
    <div className="json-view">
      <div className="json-toolbar">
        <span>{label}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            void (async () => {
              try {
                await navigator.clipboard.writeText(text);
                setCopyStatus("Copied");
              } catch {
                setCopyStatus("Copy unavailable");
              }
            })();
          }}
        >
          {copyStatus}
        </Button>
      </div>
      <pre
        tabIndex={0}
        aria-label={label}
      >
        {truncated ? text.slice(0, 12000) + "\n…" : text}
      </pre>
      {truncated ? (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setExpanded(true)}
        >
          Show full payload ({text.length.toLocaleString()} characters)
        </Button>
      ) : null}
    </div>
  );
}
