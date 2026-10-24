import { useState } from "react";
import type { ProfileField, ProjectProfile } from "../api/contract";
import { Page } from "../components/layout/Page";
import { PageHeader } from "../components/layout/PageHeader";
import { HEADER_FIELDS, SECTIONS, specFor, type SectionId } from "../components/profile/fields";
import { ProfileInput } from "../components/profile/ProfileInput";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ConfirmMissing } from "../components/ui/ConfirmMissing";
import { fieldLabel, formatFieldValue } from "../lib/format";
import { RUECKFRAGE } from "../lib/openCriteria";
import { t } from "../text/de-CH";

interface Props {
  profile: ProjectProfile;
  /** As read from the description; a corrected field shows what the description said. */
  extracted: ProjectProfile | null;
  /** From the form on page 1; not part of the profile. */
  company: string | null;
  onChange: (name: string, field: ProfileField) => void;
  busy: boolean;
  onBack: () => void;
  onConfirm: () => void;
}

const RECHTSFORM: Record<string, string> = { AG: "Aktiengesellschaft", GmbH: "Gesellschaft mit beschränkter Haftung", oeffentlich: "Öffentlich-rechtlich" };

/**
 * Fields grouped by meaning, not by status. Unknown fields go to "Weitere Angaben". Answers to criterion
 * questions (rueckfrage_*) are part of the profile but belong to the Rückfragen, so they are not shown here.
 */
function groupFields(fields: ProjectProfile["fields"]) {
  const placed = new Set([...SECTIONS.flatMap(s => s.fields), ...HEADER_FIELDS]);
  const groups: { id: SectionId; names: string[] }[] = SECTIONS.map(s => ({ id: s.id, names: s.fields.filter(f => f in fields) }));
  groups.push({ id: "weitere", names: Object.keys(fields).filter(f => !placed.has(f) && !f.startsWith(RUECKFRAGE)) });
  return groups.filter(g => g.names.length > 0);
}

/** Long text and the field that decides which programs are checked take the full width. */
function isWide(name: string) {
  const spec = specFor(name);
  return spec.kind === "textarea" || ("wide" in spec && spec.wide === true);
}

export function ProfileScreen({ profile, extracted, company, onChange, busy, onBack, onConfirm }: Props) {
  const [missing, setMissing] = useState<string[] | null>(null);
  const f = profile.fields;
  const name = company;
  const rechtsform = typeof f.rechtsform?.value === "string" ? f.rechtsform.value : null;
  const subline = [
    f.standort_gemeinde?.value && `${formatFieldValue("standort_gemeinde", f.standort_gemeinde)}${f.standort_kanton?.value ? ` ${f.standort_kanton.value}` : ""}`,
    typeof f.mitarbeitende?.value === "number" && `${f.mitarbeitende.value} Mitarbeitende`,
    f.taetigkeit?.value && formatFieldValue("taetigkeit", f.taetigkeit),
  ].filter(Boolean);
  const all = Object.entries(f)
    .filter(([n]) => !n.startsWith(RUECKFRAGE))
    .map(([, x]) => x);
  const counts = t.profile.counts(
    all.filter(x => x.status === "angegeben").length,
    all.filter(x => x.status === "annahme").length,
    all.filter(x => x.status === "fehlt").length,
  );

  /** Every field still marked "fehlt", in the order shown on the page. */
  function confirm() {
    const empty = groupFields(f)
      .flatMap(g => g.names)
      .filter(n => f[n].status === "fehlt")
      .map(fieldLabel);
    if (empty.length) setMissing(empty);
    else onConfirm();
  }

  return (
    <Page>
      <PageHeader title={t.profile.title} />

      <Card as="section" className="animate-rise divide-y divide-line p-0">
        <header className="flex flex-wrap items-center justify-between gap-x-8 gap-y-4 px-8 py-7">
          <div className="flex min-w-0 items-center gap-5">
            <span aria-hidden="true" className="grid size-16 flex-none place-items-center rounded-full bg-primary text-3xl text-white type-display">
              {name ? name.trim()[0].toUpperCase() : "?"}
            </span>
            <div className="flex min-w-0 flex-col gap-0.5">
              <p className="text-2xl type-display">{name ?? t.profile.unnamed}</p>
              <p className="text-fg-2">{[rechtsform && (RECHTSFORM[rechtsform] ?? rechtsform), ...subline].filter(Boolean).join(" · ")}</p>
            </div>
          </div>
          <p className="flex flex-wrap gap-x-5 gap-y-1 text-sm font-semibold">
            <span className="text-ok">{counts.given}</span>
            <span className="text-warn">{counts.assumed}</span>
            <span className="text-error">{counts.missing}</span>
          </p>
        </header>
        {groupFields(f).map(group => {
          const assumed = group.names.filter(n => f[n].status === "annahme");
          return (
          <div key={group.id} className="flex flex-col gap-5 px-8 py-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-2xl">{t.profile.sections[group.id]}</h2>
              {assumed.length > 0 && (
                <Button size="sm" onClick={() => assumed.forEach(n => onChange(n, { ...f[n], status: "angegeben", origin: "korrektur" }))}>
                  {t.profile.acceptAll}
                </Button>
              )}
            </div>
            <div className="grid grid-cols-1 gap-x-6 gap-y-5 md:grid-cols-2">
              {group.names.map(n => (
                <div key={n} className={isWide(n) ? "md:col-span-2" : ""}>
                  <ProfileInput name={n} field={f[n]} original={extracted?.fields[n]} onChange={field => onChange(n, field)} />
                </div>
              ))}
            </div>
          </div>
          );
        })}
      </Card>

      <div className="flex flex-wrap justify-between gap-3">
        <Button variant="secondary" onClick={onBack}>
          ← {t.common.back}
        </Button>
        <Button onClick={confirm} disabled={busy}>
          {t.profile.confirm} <span aria-hidden="true">→</span>
        </Button>
      </div>

      <ConfirmMissing
        missing={missing}
        onCancel={() => setMissing(null)}
        onConfirm={() => {
          setMissing(null);
          onConfirm();
        }}
      />
    </Page>
  );
}
