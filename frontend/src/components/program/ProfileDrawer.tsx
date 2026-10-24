import { Drawer } from "@heroui/react";
import { useState } from "react";
import type { ProfileField, ProjectProfile } from "../../api/contract";
import { shortText, type EditorField } from "../../lib/openCriteria";
import { t } from "../../text/de-CH";
import { ProfileInput } from "../profile/ProfileInput";
import { Button } from "../ui/Button";

interface Props {
  isOpen: boolean;
  programName: string;
  fields: EditorField[];
  profile: ProjectProfile;
  onClose: () => void;
  onSave: (changes: Record<string, ProfileField>) => void;
  onEditWholeProfile: () => void;
}

const EMPTY_FIELD: ProfileField = { value: null, status: "fehlt", origin: null, quote: null, note: null };

/**
 * Inline editor on the program page: only the fields that could decide this program's open criteria,
 * prefilled from the profile, empty ones highlighted, each with the criteria it is asked for.
 */
export function ProfileDrawer({ isOpen, programName, fields, profile, onClose, onSave, onEditWholeProfile }: Props) {
  const [changes, setChanges] = useState<Record<string, ProfileField>>({});
  const close = () => {
    setChanges({});
    onClose();
  };
  const changed = Object.keys(changes).length > 0;

  return (
    <Drawer.Backdrop isOpen={isOpen} onOpenChange={open => !open && close()}>
      <Drawer.Content placement="right">
        <Drawer.Dialog aria-label={t.editor.title} className="w-full sm:w-[34rem]" data-testid="profile-drawer">
          <Drawer.Header className="flex flex-col gap-2">
            <Drawer.Heading className="text-2xl">{t.editor.title}</Drawer.Heading>
            <p className="text-fg-2">{t.editor.lead(programName)}</p>
          </Drawer.Header>
          <Drawer.Body className="flex flex-col gap-6">
            {fields.map(f => (
              <div key={f.name} className={`flex flex-col gap-2 rounded-xl border px-4 py-4 ${f.missing ? "border-error/50 bg-error-soft/40" : "border-primary/40 bg-primary-soft/30"}`}>
                <ProfileInput name={f.name} field={changes[f.name] ?? profile.fields[f.name] ?? EMPTY_FIELD} onChange={field => setChanges(c => ({ ...c, [f.name]: field }))} />
                <div className="text-sm">
                  <span className="font-semibold">{t.editor.why}: </span>
                  <span className="text-fg-2">{t.editor.whyText(programName)} </span>
                  {f.criteria.map((c, i) => (
                    <span key={c.criterion_id} className="text-fg-2">
                      {i > 0 && " "}«{shortText(c.text)}»
                    </span>
                  ))}
                </div>
              </div>
            ))}
            <button type="button" onClick={onEditWholeProfile} className="self-start text-sm font-semibold text-primary-ink underline decoration-primary-ink/30 underline-offset-4 hover:decoration-primary-ink">
              {t.editor.wholeProfile}
            </button>
          </Drawer.Body>
          <Drawer.Footer className="flex flex-wrap items-center justify-end gap-3">
            {!changed && <span className="mr-auto text-sm text-fg-2">{t.editor.unchanged}</span>}
            <Button variant="secondary" onClick={close}>
              {t.editor.cancel}
            </Button>
            <Button
              disabled={!changed}
              onClick={() => {
                onSave(changes);
                setChanges({});
              }}
            >
              {t.editor.save}
            </Button>
          </Drawer.Footer>
        </Drawer.Dialog>
      </Drawer.Content>
    </Drawer.Backdrop>
  );
}
