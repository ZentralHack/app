import { AlertDialog } from "@heroui/react";
import { t } from "../../text/de-CH";
import { Button } from "./Button";

interface Props {
  /** Labels of the inputs that are still empty; `null` keeps the dialog closed. */
  missing: string[] | null;
  onCancel: () => void;
  onConfirm: () => void;
}

/** Asks before continuing with empty inputs and names each of them. */
export function ConfirmMissing({ missing, onCancel, onConfirm }: Props) {
  return (
    <AlertDialog.Backdrop isOpen={missing !== null} onOpenChange={open => !open && onCancel()}>
      <AlertDialog.Container size="md">
        <AlertDialog.Dialog>
          <AlertDialog.Header>
            <AlertDialog.Icon status="warning" />
            <AlertDialog.Heading>{t.missing.title}</AlertDialog.Heading>
          </AlertDialog.Header>
          <AlertDialog.Body className="flex flex-col gap-3">
            <p>{t.missing.lead}</p>
            <ul className="m-0 flex list-disc flex-col gap-1 pl-5">
              {missing?.map(label => (
                <li key={label}>{label}</li>
              ))}
            </ul>
            <p className="text-fg-2">{t.missing.question}</p>
          </AlertDialog.Body>
          <AlertDialog.Footer>
            <Button variant="secondary" onClick={onCancel}>
              {t.missing.complete}
            </Button>
            <Button onClick={onConfirm}>{t.missing.continue}</Button>
          </AlertDialog.Footer>
        </AlertDialog.Dialog>
      </AlertDialog.Container>
    </AlertDialog.Backdrop>
  );
}
