import type { HTMLAttributes } from "react";

interface Props extends HTMLAttributes<HTMLElement> {
  as?: "div" | "article" | "section";
}

/** Flat white surface with a hairline border. No shadow at rest. */
export function Card({ as: Tag = "div", className = "", ...rest }: Props) {
  return <Tag className={`rounded-xl border border-line bg-surface p-(--pad-card) ${className}`} {...rest} />;
}
