import { Button as HeroButton } from "@heroui/react";
import type { ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost";
type Size = "md" | "sm";

const VARIANT = { primary: "primary", secondary: "outline", ghost: "ghost" } as const;
const SIZE = { md: "md", sm: "sm" } as const;

interface Props {
  variant?: Variant;
  size?: Size;
  type?: "button" | "submit";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
  "aria-label"?: string;
  "data-testid"?: string;
  children: ReactNode;
}

/** HeroUI button with the app's variant names. */
export function Button({ variant = "primary", size = "md", type = "button", disabled, onClick, className = "", children, ...aria }: Props) {
  return (
    <HeroButton variant={VARIANT[variant]} size={SIZE[size]} type={type} isDisabled={disabled} onPress={onClick} className={`font-semibold ${className}`} {...aria}>
      {children}
    </HeroButton>
  );
}
