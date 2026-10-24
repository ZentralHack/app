import { ComboBox, Description, FieldError, Input, InputGroup, Label, ListBox, TextArea, TextField } from "@heroui/react";
import { useState } from "react";
import type { Clarification } from "../api/contract";
import { Page } from "../components/layout/Page";

/** The backend accepts at most this many characters (ProfileRequest.text). */
const MAX_TEXT = 5000;
import { PageHeader } from "../components/layout/PageHeader";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { Spinner } from "../components/ui/Spinner";
import { ConfirmMissing } from "../components/ui/ConfirmMissing";
import { Card } from "../components/ui/Card";
import { GEMEINDEN } from "../content/gemeinden";
import { RECHTSFORMEN } from "../content/rechtsformen";
import { groupDigits } from "../lib/format";
import { t } from "../text/de-CH";

export interface CaptureDraft {
  name: string;
  rechtsform: string;
  gruendungsjahr: string;
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
      <PageHeader title={t.capture.title} lead={t.capture.lead} />

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

        <TextField isRequired value={draft.text} onChange={text => set({ text })} isInvalid={errors.text} maxLength={MAX_TEXT}>
          <Label>{t.capture.label}</Label>
          <TextArea rows={5} placeholder="Wir sind ein KMU aus … und möchten …" />
          {errors.text ? <FieldError>{length === 0 ? t.missing.required : t.capture.tooShort}</FieldError> : <Description>{length > MAX_TEXT - 500 ? t.capture.limit(length, MAX_TEXT) : t.capture.note}</Description>}
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

        <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6">
          {busy ? (
            <span role="status" aria-live="polite" className="flex items-center gap-2 font-semibold" data-testid="capture-busy">
              <Spinner />
              {t.capture.working}
            </span>
          ) : (
            <span className="text-fg-2">{t.capture.duration}</span>
          )}
          <Button onClick={submit} disabled={busy}>
            {busy ? t.capture.submitting : t.capture.submit} {!busy && <span aria-hidden="true">→</span>}
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
