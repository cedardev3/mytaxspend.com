"use client";

import { formatMillions } from "@/lib/spend";

export type InterestDefensePair = {
  interest: { name: string; amountMillions: number };
  defense: { name: string; amountMillions: number };
};

type InterestDefenseCompareProps = {
  pair: InterestDefensePair;
};

export default function InterestDefenseCompare({ pair }: InterestDefenseCompareProps) {
  const { interest, defense } = pair;
  const larger = Math.max(interest.amountMillions, defense.amountMillions);
  const interestShare = interest.amountMillions / larger;
  const defenseShare = defense.amountMillions / larger;
  const ratio = interest.amountMillions / defense.amountMillions;
  const interestLeads = interest.amountMillions >= defense.amountMillions;

  return (
    <section
      aria-label={`${interest.name} versus ${defense.name}`}
      className="flex h-full flex-col justify-center rounded-2xl border border-[#eadfce] bg-white/80 px-3 py-2.5"
    >
      <p className="text-[10px] font-medium uppercase tracking-wide text-[#8a7358]">
        Interest vs defense payments
      </p>
      <p className="mt-0.5 text-[11px] leading-4 text-[#5c6b73]">
        {interestLeads ? (
          <>
            Interest{" "}
            <span className="font-semibold tabular-nums text-[#1f3d4d]">
              {ratio.toFixed(2)}×
            </span>{" "}
            defense
          </>
        ) : (
          <>
            Defense{" "}
            <span className="font-semibold tabular-nums text-[#1f3d4d]">
              {(1 / ratio).toFixed(2)}×
            </span>{" "}
            interest
          </>
        )}
      </p>

      <div className="mt-2.5 grid gap-2.5">
        <CompareBar
          label="Interest"
          amount={interest.amountMillions}
          share={interestShare}
          color="#6b5b95"
        />
        <CompareBar
          label="Defense"
          amount={defense.amountMillions}
          share={defenseShare}
          color="#c45c26"
        />
      </div>
    </section>
  );
}

function CompareBar({
  label,
  amount,
  share,
  color,
}: {
  label: string;
  amount: number;
  share: number;
  color: string;
}) {
  const widthPct = Math.min(Math.max(share, 0), 1) * 100;

  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <p className="truncate text-[11px] text-[#5c6b73]">{label}</p>
        <p className="shrink-0 text-[11px] font-semibold tabular-nums text-[#1f3d4d]">
          {formatMillions(amount)}
        </p>
      </div>
      <div
        className="h-2.5 overflow-hidden rounded-full bg-[#eadfce]/80 shadow-[inset_0_1px_1px_rgba(31,61,77,0.06)]"
        role="img"
        aria-label={`${label} ${formatMillions(amount)}`}
      >
        <div
          className="h-full rounded-full transition-[width] duration-500 ease-out"
          style={{
            width: `${widthPct}%`,
            background: `linear-gradient(90deg, ${color}cc 0%, ${color} 100%)`,
            boxShadow: `inset 0 1px 0 rgba(255,255,255,0.25)`,
          }}
        />
      </div>
    </div>
  );
}
