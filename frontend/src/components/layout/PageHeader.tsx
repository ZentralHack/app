import type { ReactNode } from "react";

interface Props {
  title: string;
  lead?: string;
  children?: ReactNode;
}

export function PageHeader({ title, lead, children }: Props) {
  return (
    <div className="flex max-w-[52em] flex-col gap-4">
      <h1>{title}</h1>
      {lead && <p className="text-lg">{lead}</p>}
      {children}
    </div>
  );
}
