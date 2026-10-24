import { ComboBox, Description, FieldError, Input, InputGroup, Label, ListBox, TextArea, TextField } from "@heroui/react";
import { useState } from "react";
import type { Clarification } from "../api/contract";
import { Page } from "../components/layout/Page";
import { PageHeader } from "../components/layout/PageHeader";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { ConfirmMissing } from "../components/ui/ConfirmMissing";
import { Card } from "../components/ui/Card";
import { EXAMPLES } from "../content/examples";
import { GEMEINDEN } from "../content/gemeinden";
import { RECHTSFORMEN } from "../content/rechtsformen";
import { groupDigits } from "../lib/format";
import { t } from "../text/de-CH";

/** Answer to a quick yes/no question on page 1; "" = not answered. */
export type Tri = "ja" | "nein" | "weiss_nicht" | "";
export const QUICK_FIELDS = ["sitz_schweiz_uid", "umsatz_mind_100k", "kreditwuerdig", "co2_befreit"] as const;
export type QuickField = (typeof QUICK_FIELDS)[number];

export interface CaptureDraft {
  name: string;
  rechtsform: string;
  gruendungsjahr: string;
  quick: Record<QuickField, Tri>;
  text: string;
  gemeinde: string;
  mitarbeitende: string;
  budget: string;
}

export const MIN_LENGTH = 20;

interface Props {
  draft: CaptureDraft;
  onDraftChange: (draft: CaptureDraft) => void;
  clarification: Clarification | null;
  busy: boolean;
  onSubmit: () => void;
}

export function CaptureScreen({ draft, onDraftChange, clarification, busy, onSubmit }: Props) {
  const [checked, setChecked] = useState(false);
  const [missing, setMissing] = useState<string[] | null>(null);
  const set = (patch: Partial<CaptureDraft>) => onDraftChange({ ...draft, ...patch });
  const length = draft.text.trim().length;
  // Required inputs block; their errors show once the user tried to continue (or, for the text, while typing).
  const errors = {
    text: length < MIN_LENGTH && (checked || length > 0),
    gemeinde: checked && draft.gemeinde.trim() === "",
    mitarbeitende: checked && draft.mitarbeitende === "",
  };
  const optional: [string, boolean][] = [
    [t.capture.name, draft.name.trim() === ""],
    [t.capture.rechtsform, draft.rechtsform.trim() === ""],
    [t.capture.founded, draft.gruendungsjahr.length !== 4],
    [t.capture.budget, draft.budget === ""],
    ...QUICK_FIELDS.map((f): [string, boolean] => [t.capture.quickQuestions[f], draft.quick[f] === ""]),
  ];

  function submit() {
    setChecked(true);
    if (length < MIN_LENGTH || draft.gemeinde.trim() === "" || draft.mitarbeitende === "") return;
    const empty = optional.filter(([, isEmpty]) => isEmpty).map(([label]) => label);
    if (empty.length) setMissing(empty);
    else onSubmit();
  }

  return (
    <Page>
      <div className="grid grid-cols-1 items-start gap-8 xl:grid-cols-[minmax(0,1fr)_auto]">
        <PageHeader title={t.capture.title} lead={t.capture.lead} />

        <section aria-labelledby="examples-title" className="flex flex-col gap-2 justify-self-start rounded-xl border border-line bg-surface p-3 xl:justify-self-end">
          <h2 id="examples-title" className="px-1 text-sm">
            {t.capture.examples}
          </h2>
          <div className="flex flex-wrap gap-1.5 xl:flex-col">
            {EXAMPLES.map(ex => (
              <button
                key={ex.label}
                type="button"
                aria-pressed={draft.text === ex.text}
                onClick={() => set({ text: ex.text, name: ex.company, rechtsform: ex.rechtsform, gruendungsjahr: ex.gruendungsjahr, gemeinde: ex.gemeinde, mitarbeitende: ex.mitarbeitende, budget: ex.budget, quick: { ...ex.quick } })}
                className="rounded-md border border-line px-2.5 py-1 text-left text-sm transition-colors hover:border-line-strong hover:bg-bg aria-pressed:border-primary aria-pressed:bg-primary-soft aria-pressed:text-primary-ink"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </section>
      </div>

      <Card as="section" className="flex flex-col gap-6">
        {clarification && (
          <Alert tone="info">
            <b>{t.capture.clarify}</b> {clarification.question} {clarification.options.join(", ")}?
          </Alert>
        )}

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            <TextField value={draft.name} onChange={name => set({ name })}>
              <Label>{t.capture.name}</Label>
              <Input placeholder="z. B. Muster AG" />
            </TextField>
            <ComboBox allowsCustomValue inputValue={draft.rechtsform} onInputChange={rechtsform => set({ rechtsform })}>
              <Label>{t.capture.rechtsform}</Label>
              <ComboBox.InputGroup>
                <Input placeholder="z. B. AG" />
                <ComboBox.Trigger />
              </ComboBox.InputGroup>
              <ComboBox.Popover>
                <ListBox>
                  {RECHTSFORMEN.map(r => (
                    <ListBox.Item key={r} id={r} textValue={r}>
                      {r}
                    </ListBox.Item>
                  ))}
                </ListBox>
              </ComboBox.Popover>
            </ComboBox>
            <TextField value={draft.gruendungsjahr} onChange={v => set({ gruendungsjahr: v.replace(/\D/g, "").slice(0, 4) })}>
              <Label>{t.capture.founded}</Label>
              <Input inputMode="numeric" placeholder="z. B. 2019" />
            </TextField>
        </div>

        <TextField isRequired value={draft.text} onChange={text => set({ text })} isInvalid={errors.text}>
          <Label>{t.capture.label}</Label>
          <TextArea rows={5} placeholder="Wir sind ein KMU aus … und möchten …" />
          {errors.text ? <FieldError>{length === 0 ? t.missing.required : t.capture.tooShort}</FieldError> : <Description>{t.capture.note}</Description>}
        </TextField>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <ComboBox isRequired isInvalid={errors.gemeinde} allowsCustomValue inputValue={draft.gemeinde} onInputChange={gemeinde => set({ gemeinde })}>
            <Label>{t.capture.gemeinde}</Label>
            <ComboBox.InputGroup>
              <Input placeholder="Gemeinde suchen" />
              <ComboBox.Trigger />
            </ComboBox.InputGroup>
            <ComboBox.Popover>
              <ListBox>
                {GEMEINDEN.map(g => (
                  <ListBox.Item key={g} id={g} textValue={g}>
                    {g}
                  </ListBox.Item>
                ))}
              </ListBox>
            </ComboBox.Popover>
            {errors.gemeinde && <FieldError>{t.missing.required}</FieldError>}
          </ComboBox>

          <TextField isRequired isInvalid={errors.mitarbeitende} value={draft.mitarbeitende} onChange={v => set({ mitarbeitende: v.replace(/\D/g, "") })}>
            <Label>{t.capture.employees}</Label>
            <InputGroup>
              <InputGroup.Input inputMode="numeric" placeholder="18" />
              <InputGroup.Suffix>{t.capture.persons}</InputGroup.Suffix>
            </InputGroup>
            {errors.mitarbeitende && <FieldError>{t.missing.required}</FieldError>}
          </TextField>

          <TextField value={draft.budget} onChange={v => set({ budget: groupDigits(v) })}>
            <Label>
              {t.capture.budget} <span className="font-normal text-fg-muted">{t.common.optional}</span>
            </Label>
            <InputGroup>
              <InputGroup.Prefix>CHF</InputGroup.Prefix>
              <InputGroup.Input inputMode="numeric" placeholder="400'000" className="pl-2" />
            </InputGroup>
          </TextField>
        </div>

        <fieldset className="flex flex-col">
          <legend className="mb-2 text-sm font-semibold">{t.capture.quick}</legend>
          <div className="flex flex-col divide-y divide-line">
            {QUICK_FIELDS.map(f => (
              <div key={f} className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-2.5">
                <span id={`quick-${f}`}>{t.capture.quickQuestions[f]}</span>
                <YesNo labelledBy={`quick-${f}`} value={draft.quick[f]} onChange={v => set({ quick: { ...draft.quick, [f]: v } })} />
              </div>
            ))}
          </div>
        </fieldset>

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6">
          <span className="text-fg-2">{t.capture.duration}</span>
          <Button onClick={submit} disabled={busy}>
            {t.capture.submit} <span aria-hidden="true">→</span>
          </Button>
        </div>
      </Card>

      <ConfirmMissing
        missing={missing}
        onCancel={() => setMissing(null)}
        onConfirm={() => {
          setMissing(null);
          onSubmit();
        }}
      />
    </Page>
  );
}

/** Three-way segmented control: Ja / Nein / Weiss nicht. Clicking the active option clears it. */
function YesNo({ labelledBy, value, onChange }: { labelledBy: string; value: Tri; onChange: (v: Tri) => void }) {
  const options: [Exclude<Tri, "">, string][] = [
    ["ja", t.capture.yes],
    ["nein", t.capture.no],
    ["weiss_nicht", t.capture.unknown],
  ];
  return (
    <div role="radiogroup" aria-labelledby={labelledBy} className="inline-flex overflow-hidden rounded-lg border border-line-strong">
      {options.map(([id, label]) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={value === id}
          onClick={() => onChange(value === id ? "" : id)}
          className="border-l border-line-strong px-3.5 py-1.5 text-sm transition-colors first:border-l-0 hover:bg-bg aria-checked:bg-primary-soft aria-checked:font-semibold aria-checked:text-primary-ink"
        >
          {label}
        </button>
      ))}
    </div>
  );
}
