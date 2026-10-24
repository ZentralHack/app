import logo from "../../assets/logo.svg";
import { t } from "../../text/de-CH";
import { Roadmap, RoadmapCompact } from "./Roadmap";

interface Props {
  step: number;
  reachable: number;
  onNavigate: (step: number) => void;
}

function Brand() {
  return <img src={logo} alt={t.app.name} className="h-11 w-auto self-start" />;
}

/** Left column on wide screens (brand, roadmap); a slim top block on narrow screens. */
export function Sidebar({ step, reachable, onNavigate }: Props) {
  return (
    <aside className="border-line bg-surface max-lg:border-b lg:sticky lg:top-0 lg:h-screen lg:w-(--sidebar-w) lg:flex-none lg:border-r print:hidden">
      <div className="flex h-full flex-col gap-8 px-6 py-4 lg:px-7 lg:pt-5 lg:pb-8">
        <Brand />
        <nav aria-label={t.app.roadmap} className="max-lg:hidden lg:mt-4">
          <Roadmap current={step} reachable={reachable} onNavigate={onNavigate} />
        </nav>
        <div className="lg:hidden">
          <RoadmapCompact current={step} />
        </div>
      </div>
    </aside>
  );
}
