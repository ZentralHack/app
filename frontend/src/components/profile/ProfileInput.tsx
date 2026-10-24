import { Calendar, ComboBox, DateField, DatePicker, Input, InputGroup, ListBox, Select, TextArea, TextField } from "@heroui/react";
import { parseDate, type DateValue } from "@internationalized/date";
import { useState, type KeyboardEvent, type ReactNode } from "react";
import { I18nProvider } from "react-aria-components";
import type { ProfileField } from "../../api/contract";
import { fieldLabel, formatChf, groupDigits, parseChf } from "../../lib/format";
import { t } from "../../text/de-CH";
import { optionId, specFor, withValue, type FieldSpec } from "./fields";

interface Props {
  name: string;
  field: ProfileField;
  onChange: (field: ProfileField) => void;
  /** What the profile step read from the description; shown when the user has changed the value. */
  original?: ProfileField;
}

type Value = ProfileField["value"];

const isEmpty = (v: Value) => v === null || (typeof v === "string" && v.trim() === "") || (Array.isArray(v) && v.length === 0);
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/**
 * One profile field as a plain input with its label above and the status in colour below.
 * Typing or picking makes the field "angegeben". An assumption can be confirmed with the button inside the field.
 * Nothing has a default: an empty field shows "Bitte wählen" and stays "fehlt" until the user picks something.
 */
export function ProfileInput({ name, field, onChange, original }: Props) {
  const spec = specFor(name);
  const id = `pf-${name}`;
  const set = (value: Value) =>
    onChange({ value: isEmpty(value) ? null : value, status: isEmpty(value) ? "fehlt" : "angegeben", origin: "korrektur", quote: null, note: null });
  const confirm = field.status === "annahme" ? () => onChange({ ...field, status: "angegeben", origin: "korrektur" }) : null;

  return (
    <div className="flex flex-col gap-1.5">
      <span id={`${id}-label`} className="text-sm font-semibold">
        {fieldLabel(name)}
      </span>
      {"hint" in spec && spec.hint && <span className="-mt-1 text-sm text-fg-2">{spec.hint}</span>}
      <div className="relative">
        <Control id={id} spec={spec} field={field} set={set} padRight={confirm !== null && spec.kind !== "yesno"} />
        {confirm && spec.kind !== "yesno" && (
          <span className={`pointer-events-none absolute flex items-center ${spec.kind === "textarea" ? "right-3 bottom-2.5" : "inset-y-0"} ${OVERLAY_RIGHT[spec.kind]}`}>
            <button
              type="button"
              onClick={confirm}
              className="pointer-events-auto flex items-center gap-1 rounded px-1 text-sm font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 transition-colors hover:decoration-primary-ink"
            >
              {t.profile.accept}
            </button>
          </span>
        )}
      </div>
      <StatusLine field={field} original={original} onConfirm={spec.kind === "yesno" ? confirm : null} />
    </div>
  );
}

/**
 * A closed dropdown would change its value on a single letter or arrow key (typeahead), without opening.
 * That turned "Ja" into "Nein" by accident once; choosing has to happen in the open list.
 */
function blockClosedKeys(e: KeyboardEvent) {
  const target = e.target as HTMLElement;
  if (target.getAttribute("aria-expanded") === "true") return;
  if (e.key.length === 1 || e.key === "ArrowLeft" || e.key === "ArrowRight") {
    if (e.key === " ") return; // space opens the list
    e.stopPropagation();
  }
}

/** Space the confirm button keeps free for the field's own indicator (chevron, calendar). */
const OVERLAY_RIGHT: Record<FieldSpec["kind"], string> = {
  text: "right-3",
  textarea: "",
  number: "right-3",
  select: "right-10",
  multi: "right-10",
  combo: "right-10",
  yesno: "",
  date: "right-11",
};

function Control({ id, spec, field, set, padRight }: { id: string; spec: FieldSpec; field: ProfileField; set: (v: Value) => void; padRight: boolean }) {
  const labelledBy = `${id}-label`;
  const pad = padRight ? "pr-32" : "";
  const placeholder = "placeholder" in spec && spec.placeholder ? spec.placeholder : t.profile.choose;

  if (spec.kind === "yesno") {
    // Two explicit buttons instead of a dropdown: a click is the only way to set or change the value.
    const current = field.value === null ? null : field.value === true || field.value === "Ja";
    return (
      <div role="radiogroup" aria-labelledby={labelledBy} className="flex gap-2" data-yesno={id}>
        {[true, false].map(v => (
          <button
            key={String(v)}
            type="button"
            role="radio"
            aria-checked={current === v}
            onClick={() => set(current === v ? null : v)}
            className="h-10 min-w-24 rounded-lg border border-line-strong bg-surface px-4 font-semibold transition-colors hover:border-primary aria-checked:border-primary aria-checked:bg-primary-soft aria-checked:text-primary-ink"
          >
            {v ? t.profile.yes : t.profile.no}
          </button>
        ))}
      </div>
    );
  }

  if (spec.kind === "select") {
    const options = spec.options;
    const current = field.value === null ? null : optionId(spec.options, String(field.value));
    const list = withValue(options, current ? [current] : []);
    return (
      <div onKeyDownCapture={blockClosedKeys}>
        <Select aria-labelledby={labelledBy} value={current} onChange={key => set(key === null ? null : String(key))} placeholder={placeholder} fullWidth>
          <Select.Trigger className={pad}>
            <Select.Value />
            <Select.Indicator />
          </Select.Trigger>
          <Popover>
            {list.map(o => (
              <ListBox.Item key={o.id} id={o.id} textValue={o.label}>
                {o.label}
                <ListBox.ItemIndicator />
              </ListBox.Item>
            ))}
          </Popover>
        </Select>
      </div>
    );
  }

  if (spec.kind === "multi") {
    const values = Array.isArray(field.value) ? field.value.map(String) : [];
    const list = withValue(spec.options, values);
    const selected = values.map(v => optionId(list, v));
    return (
      <div onKeyDownCapture={blockClosedKeys}>
        <Select
          aria-labelledby={labelledBy}
          selectionMode="multiple"
          value={selected}
          onChange={keys => set((keys as (string | number)[]).map(String))}
          placeholder={placeholder}
          fullWidth
        >
          <Select.Trigger className={pad}>
            <Select.Value />
            <Select.Indicator />
          </Select.Trigger>
          <Popover multiple>
            {list.map(o => (
              <ListBox.Item key={o.id} id={o.id} textValue={o.label}>
                {o.label}
                <ListBox.ItemIndicator />
              </ListBox.Item>
            ))}
          </Popover>
        </Select>
      </div>
    );
  }

  if (spec.kind === "combo") {
    return (
      <ComboBox aria-labelledby={labelledBy} allowsCustomValue inputValue={field.value === null ? "" : String(field.value)} onInputChange={v => set(v)} fullWidth>
        <ComboBox.InputGroup>
          <Input placeholder={placeholder} className={pad} />
          <ComboBox.Trigger />
        </ComboBox.InputGroup>
        <ComboBox.Popover>
          <ListBox>
            {spec.options.map(o => (
              <ListBox.Item key={o} id={o} textValue={o}>
                {o}
              </ListBox.Item>
            ))}
          </ListBox>
        </ComboBox.Popover>
      </ComboBox>
    );
  }

  if (spec.kind === "date") {
    const value = typeof field.value === "string" && ISO_DATE.test(field.value) ? parseDate(field.value) : null;
    return (
      <I18nProvider locale="de-CH">
        <DatePicker aria-labelledby={labelledBy} value={value} onChange={(d: DateValue | null) => set(d ? d.toString() : null)}>
          <DateField.Group fullWidth className={pad}>
            <DateField.Input>{segment => <DateField.Segment segment={segment} />}</DateField.Input>
            <DateField.Suffix>
              <DatePicker.Trigger>
                <DatePicker.TriggerIndicator />
              </DatePicker.Trigger>
            </DateField.Suffix>
          </DateField.Group>
          <DatePicker.Popover>
            <Calendar aria-label={t.profile.calendar}>
              <Calendar.Header>
                <Calendar.YearPickerTrigger>
                  <Calendar.YearPickerTriggerHeading />
                </Calendar.YearPickerTrigger>
                <Calendar.NavButton slot="previous" />
                <Calendar.NavButton slot="next" />
              </Calendar.Header>
              <Calendar.Grid>
                <Calendar.GridHeader>{day => <Calendar.HeaderCell>{day}</Calendar.HeaderCell>}</Calendar.GridHeader>
                <Calendar.GridBody>{date => <Calendar.Cell date={date} />}</Calendar.GridBody>
              </Calendar.Grid>
              <Calendar.YearPickerGrid>
                <Calendar.YearPickerGridBody>{({ year }) => <Calendar.YearPickerCell year={year} />}</Calendar.YearPickerGridBody>
              </Calendar.YearPickerGrid>
            </Calendar>
          </DatePicker.Popover>
        </DatePicker>
      </I18nProvider>
    );
  }

  if (spec.kind === "number") return <NumberInput labelledBy={labelledBy} spec={spec} field={field} set={set} pad={pad} />;

  const text = field.value === null ? "" : Array.isArray(field.value) ? field.value.join(", ") : String(field.value);
  return (
    <TextField aria-labelledby={labelledBy} value={text} onChange={v => set(v)} fullWidth>
      {spec.kind === "textarea" ? <TextArea rows={3} placeholder={placeholder} className="pb-9" /> : <Input placeholder={placeholder} className={pad} />}
    </TextField>
  );
}

/** Dropdown list; shared by single and multiple selects. */
function Popover({ multiple, children }: { multiple?: boolean; children: ReactNode }) {
  return (
    <Select.Popover>
      <ListBox selectionMode={multiple ? "multiple" : "single"}>{children}</ListBox>
    </Select.Popover>
  );
}

/** Formats while typing: CHF amounts get thousands separators, other numbers stay digits only. */
function NumberInput({ labelledBy, spec, field, set, pad }: { labelledBy: string; spec: Extract<FieldSpec, { kind: "number" }>; field: ProfileField; set: (v: Value) => void; pad: string }) {
  const grouped = spec.prefix === "CHF";
  const [text, setText] = useState(typeof field.value === "number" ? (grouped ? formatChf(field.value) : String(field.value)) : "");
  return (
    <TextField
      aria-labelledby={labelledBy}
      value={text}
      onChange={v => {
        const next = grouped ? groupDigits(v) : v.replace(/\D/g, "").slice(0, spec.maxDigits ?? 12);
        setText(next);
        set(parseChf(next));
      }}
      fullWidth
    >
      <InputGroup className={pad}>
        {spec.prefix && <InputGroup.Prefix>{spec.prefix}</InputGroup.Prefix>}
        <InputGroup.Input inputMode="numeric" placeholder={spec.placeholder} />
        {spec.suffix && <InputGroup.Suffix>{spec.suffix}</InputGroup.Suffix>}
      </InputGroup>
    </TextField>
  );
}

/** Coloured status text under the input: green angegeben, amber Annahme, red fehlt. */
function StatusLine({ field, original, onConfirm }: { field: ProfileField; original?: ProfileField; onConfirm: (() => void) | null }) {
  const changedFromText =
    field.origin === "korrektur" && original?.status === "angegeben" && original.quote && JSON.stringify(original.value) !== JSON.stringify(field.value) ? original.quote : null;
  if (field.status === "angegeben") {
    const detail = field.quote
      ? `«${field.quote}»`
      : field.origin === "formular"
        ? t.profile.fromForm
        : field.origin === "rueckfrage"
          ? t.profile.fromAnswer
          : field.origin === "korrektur"
            ? t.profile.edited
            : null;
    return (
      <p className="text-sm text-ok">
        {t.profile.given}
        {detail && <span className="text-fg-2"> · {detail}</span>}
        {changedFromText && <span className="block text-warn">{t.profile.textSaid(changedFromText)}</span>}
      </p>
    );
  }
  if (field.status === "annahme") {
    return (
      <p className="text-sm text-warn">
        {t.profile.assumed} · {(field.note ?? t.profile.derived).replace(/\.$/, "")}. {t.profile.pleaseCheck}
        {onConfirm && (
          <button type="button" onClick={onConfirm} className="ml-2 font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 hover:decoration-primary-ink">
            {t.profile.accept}
          </button>
        )}
      </p>
    );
  }
  return (
    <p className="text-sm text-error">
      {t.profile.missing}
      {field.note && <span className="text-fg-2"> · {field.note}</span>}
    </p>
  );
}
