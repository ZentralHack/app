import { Dropdown } from "@heroui/react";
import { downloadIcs, googleCalendarUrl, outlookCalendarUrl, type CalendarEvent } from "../../lib/ics";
import { t } from "../../text/de-CH";
import { CalendarPlus } from "./icons";

type Target = "google" | "outlook" | "ics";

/**
 * Icon-only button in the primary colour; opens a menu: Google Kalender and Outlook open a prefilled event in a
 * new tab, "Apple / andere" downloads the .ics file. Same height as the default button.
 */
export function CalendarButton({ event, filename, size = "md" }: { event: CalendarEvent; filename: string; size?: "md" | "sm" }) {
  const open = (target: Target) => {
    if (target === "ics") downloadIcs(filename, [event]);
    else window.open(target === "google" ? googleCalendarUrl(event) : outlookCalendarUrl(event), "_blank", "noopener");
  };
  return (
    <Dropdown>
      <Dropdown.Trigger
        aria-label={t.calendar.add}
        className={`inline-flex flex-none items-center justify-center rounded-full border border-primary/50 bg-surface text-primary-ink transition-colors hover:bg-primary-soft ${size === "sm" ? "size-8" : "size-10"}`}
        data-testid="calendar"
      >
        <span title={t.calendar.add} className="grid size-full place-items-center">
          <CalendarPlus aria-hidden="true" className={size === "sm" ? "size-4" : "size-5"} />
        </span>
      </Dropdown.Trigger>
      <Dropdown.Popover placement="bottom start">
        <Dropdown.Menu aria-label={t.calendar.add} onAction={key => open(key as Target)} data-testid="calendar-menu">
          <Dropdown.Item id="google" textValue={t.calendar.google}>
            {t.calendar.google}
          </Dropdown.Item>
          <Dropdown.Item id="outlook" textValue={t.calendar.outlook}>
            {t.calendar.outlook}
          </Dropdown.Item>
          <Dropdown.Item id="ics" textValue={t.calendar.ics}>
            {t.calendar.ics}
          </Dropdown.Item>
        </Dropdown.Menu>
      </Dropdown.Popover>
    </Dropdown>
  );
}
