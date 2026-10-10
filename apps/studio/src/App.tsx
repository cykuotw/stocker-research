import { useState, type FormEvent } from "react";
import { Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FieldLabel } from "@/components/ui/field";
import { Workspace } from "@/components/runtime/workspace";
import { normalizeUrl } from "@/runtime/client";

function initialUrl() {
  try {
    const saved = localStorage.getItem("stocker.studio.v1.service");
    if (saved) return normalizeUrl(saved);
  } catch {
    /* optional browser storage */
  }
  return location.port === "5173" || location.port === "3000"
    ? "http://127.0.0.1:8000"
    : location.origin;
}
export default function App() {
  const [url, setUrl] = useState(initialUrl);
  const [draft, setDraft] = useState(url);
  const [error, setError] = useState("");
  const connect = (event: FormEvent) => {
    event.preventDefault();
    try {
      const next = normalizeUrl(draft);
      setUrl(next);
      setDraft(next);
      setError("");
      try {
        localStorage.setItem("stocker.studio.v1.service", next);
      } catch {
        /* optional browser storage */
      }
    } catch (error) {
      setError(String(error));
    }
  };
  return (
    <div className="studio-shell">
      <header className="studio-toolbar">
        <a
          className="studio-brand"
          href="/"
        >
          <Activity aria-hidden="true" />
          <span>Stocker Studio</span>
        </a>
        <form
          className="service-form"
          onSubmit={connect}
        >
          <Field orientation="horizontal">
            <FieldLabel htmlFor="service-url">Service</FieldLabel>
            <Input
              id="service-url"
              aria-invalid={Boolean(error)}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="http://127.0.0.1:8000"
            />
            <Button
              variant="outline"
              type="submit"
            >
              Connect
            </Button>
          </Field>
        </form>
      </header>
      {error ? (
        <p
          role="alert"
          className="service-error"
        >
          {error}
        </p>
      ) : null}
      <Workspace
        key={url}
        url={url}
      />
    </div>
  );
}
