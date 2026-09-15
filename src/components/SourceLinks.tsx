import type { SourceLink } from "@/lib/spend";

export default function SourceLinks({ sources }: { sources: SourceLink[] }) {
  return (
    <ul className="flex flex-col gap-1">
      {sources.map((source) => (
        <li key={source.url}>
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] leading-4 text-[#2a6f97] underline-offset-2 hover:underline"
            onClick={(event) => event.stopPropagation()}
          >
            {source.label}
          </a>
        </li>
      ))}
    </ul>
  );
}
