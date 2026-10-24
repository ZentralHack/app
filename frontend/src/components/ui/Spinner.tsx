export function Spinner({ label }: { label?: string }) {
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className="m-[3px] inline-block size-3.5 flex-none animate-spin rounded-full border-2 border-primary-soft border-t-primary"
    />
  );
}
