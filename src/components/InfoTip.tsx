"use client";

import type { ReactNode } from "react";

type InfoTipProps = {
  label: string;
  children: ReactNode;
  align?: "left" | "right";
};

export default function InfoTip({ label, children, align = "left" }: InfoTipProps) {
  return (
    <details className="info-tip relative inline-block">
      <summary
        className="inline-flex h-6 w-6 cursor-pointer items-center justify-center rounded-full border border-[#d7c9b3] bg-white text-[11px] font-semibold text-[#5c6b73] hover:border-[#2a6f97] hover:text-[#1f3d4d]"
        aria-label={label}
        onClick={(event) => event.stopPropagation()}
      >
        i
      </summary>
      <div
        className={`absolute top-[calc(100%+0.4rem)] z-40 w-[min(18rem,calc(100vw-2rem))] rounded-xl border border-[#eadfce] bg-[#fffdf8] p-3 text-left shadow-lg ${align === "right" ? "right-0" : "left-0"}`}
      >
        {children}
      </div>
    </details>
  );
}
