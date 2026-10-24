import kantonLogo from "../../assets/brand/kanton-luzern.svg";

/** The official Kanton Luzern logo, unchanged; only its height is set, the width follows. */
export function KantonLogo({ className = "" }: { className?: string }) {
  return <img src={kantonLogo} alt="Kanton Luzern" className={`w-auto flex-none ${className}`} />;
}
