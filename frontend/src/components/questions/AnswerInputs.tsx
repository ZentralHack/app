/* Inputs for number and date answers, shared by the Rückfragen screen and the inline editor. */
import { Calendar, DateField, DatePicker, InputGroup, TextField } from "@heroui/react";
import { parseDate, type DateValue } from "@internationalized/date";
import { I18nProvider } from "react-aria-components";
import type { Question } from "../../api/contract";
import { groupDigits } from "../../lib/format";
import { t } from "../../text/de-CH";

export const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Number answer with unit; CHF amounts get thousands separators while typing. */
export function NumberAnswer({ question, value, onChange, autoFocus = true }: { question: Question; value: string; onChange: (v: string) => void; autoFocus?: boolean }) {
  const chf = question.unit === "CHF";
  return (
    <TextField aria-label={question.text} value={value} onChange={v => onChange(chf ? groupDigits(v) : v.replace(/\D/g, "").slice(0, 9))} className="max-w-xs" autoFocus={autoFocus}>
      <InputGroup>
        {chf && <InputGroup.Prefix>CHF</InputGroup.Prefix>}
        <InputGroup.Input inputMode="numeric" placeholder={t.questions.numberPlaceholder} className={chf ? "pl-2" : ""} />
        {question.unit && !chf && <InputGroup.Suffix>{question.unit}</InputGroup.Suffix>}
      </InputGroup>
    </TextField>
  );
}

/** Date answer: typed with automatic dots (TT.MM.JJJJ) or picked in the calendar. */
export function DateAnswer({ value, onChange }: { value: string; onChange: (v: string | null) => void }) {
  return (
    <I18nProvider locale="de-CH">
      <DatePicker aria-label={t.profile.calendar} value={ISO_DATE.test(value) ? parseDate(value) : null} onChange={(d: DateValue | null) => onChange(d ? d.toString() : null)} className="max-w-xs">
        <DateField.Group fullWidth>
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
