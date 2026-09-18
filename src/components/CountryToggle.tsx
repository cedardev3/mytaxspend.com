"use client";

import CountryFlag from "@/components/CountryFlag";
import {
  COUNTRIES,
  type CountryConfig,
  type CountryId,
} from "@/lib/jurisdiction";

type CountryToggleProps = {
  countryId: CountryId;
  onChange: (id: CountryId) => void;
};

export default function CountryToggle({ countryId, onChange }: CountryToggleProps) {
  return (
    <div
      role="tablist"
      aria-label="Country"
      className="inline-flex items-center gap-1"
    >
      {COUNTRIES.map((country) => (
        <CountryFlagButton
          key={country.id}
          country={country}
          active={countryId === country.id}
          onSelect={() => onChange(country.id)}
        />
      ))}
    </div>
  );
}

function CountryFlagButton({
  country,
  active,
  onSelect,
}: {
  country: CountryConfig;
  active: boolean;
  onSelect: () => void;
}) {
  const label = country.available
    ? country.name
    : `${country.name} (coming soon)`;

  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      aria-label={label}
      title={label}
      className={`flex h-7 w-9 items-center justify-center rounded-md transition-opacity ${
        active
          ? "bg-[#f4efe6] opacity-100 ring-1 ring-[#d9cbb8]"
          : "opacity-50 hover:bg-[#f7f3ec] hover:opacity-85"
      }`}
      onClick={onSelect}
    >
      <CountryFlag
        countryId={country.id}
        className="h-3.5 w-[1.35rem] rounded-[1px] shadow-[0_0_0_1px_rgba(31,61,77,0.12)]"
      />
    </button>
  );
}
