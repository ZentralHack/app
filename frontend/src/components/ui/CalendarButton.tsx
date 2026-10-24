import { Button as HeroButton } from "@heroui/react";
import { t } from "../../text/de-CH";
import { CalendarPlus } from "./icons";

/** Icon-only button in the primary colour that downloads a .ics file; same height as the default button. */
export function CalendarButton({ onClick, label = t.calendar.add, size = "md" }: { onClick: () => void; label?: string; size?: "md" | "sm" }) {
  return (
    <span title={label} className="inline-flex">
      <HeroButton
        isIconOnly
        variant="outline"
        size={size}
        aria-label={label}
        onPress={onClick}
        className="border-primary/50 text-primary-ink hover:bg-primary-soft"
        data-testid="calendar"
      >
        <CalendarPlus aria-hidden="true" className={size === "sm" ? "size-4" : "size-5"} />
      </HeroButton>
    </span>
  );
}
