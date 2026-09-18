import type { CountryId } from "@/lib/jurisdiction";

type CountryFlagProps = {
  countryId: CountryId;
  className?: string;
};

/** SVG flags — emoji flags often fail to render on Windows. */
export default function CountryFlag({ countryId, className }: CountryFlagProps) {
  if (countryId === "us") {
    return (
      <svg
        viewBox="0 0 19 10"
        className={className}
        aria-hidden
        focusable="false"
      >
        <rect width="19" height="10" fill="#b22234" />
        <rect y="0.77" width="19" height="0.77" fill="#fff" />
        <rect y="2.31" width="19" height="0.77" fill="#fff" />
        <rect y="3.85" width="19" height="0.77" fill="#fff" />
        <rect y="5.38" width="19" height="0.77" fill="#fff" />
        <rect y="6.92" width="19" height="0.77" fill="#fff" />
        <rect y="8.46" width="19" height="0.77" fill="#fff" />
        <rect width="7.6" height="5.38" fill="#3c3b6e" />
      </svg>
    );
  }

  // Official 2:1 maple-leaf geometry (Wikimedia / MapGrid construction sheet).
  return (
    <svg
      viewBox="0 0 9600 4800"
      className={className}
      aria-hidden
      focusable="false"
    >
      <path
        fill="#d52b1e"
        d="m0 0h2400l99 99h4602l99-99h2400v4800h-2400l-99-99h-4602l-99 99H0z"
      />
      <path
        fill="#fff"
        d="m2400 0h4800v4800h-4800zm2490 4430-45-863a95 95 0 0 1 111-98l859 151-116-320a65 65 0 0 1 20-73l941-762-212-99a65 65 0 0 1-34-79l186-572-542 115a65 65 0 0 1-73-38l-105-247-423 454a65 65 0 0 1-111-57l204-1052-327 189a65 65 0 0 1-91-27l-332-652-332 652a65 65 0 0 1-91 27l-327-189 204 1052a65 65 0 0 1-111 57l-423-454-105 247a65 65 0 0 1-73 38l-542-115 186 572a65 65 0 0 1-34 79l-212 99 941 762a65 65 0 0 1 20 73l-116 320 859-151a95 95 0 0 1 111 98l-45 863z"
      />
    </svg>
  );
}
