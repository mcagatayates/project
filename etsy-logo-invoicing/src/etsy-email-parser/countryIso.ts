/**
 * Deliberately small, explicit lookup — NOT an attempt to cover every
 * country. Unknown country names resolve to null (never guessed), which
 * surfaces as a parseWarning and, downstream, blocks invoicing until a
 * human resolves it. Extend this table as real orders surface new
 * countries.
 */
const COUNTRY_NAME_TO_ISO2: Record<string, string> = {
  "united states": "US",
  "united states of america": "US",
  usa: "US",
  "united kingdom": "GB",
  uk: "GB",
  "great britain": "GB",
  germany: "DE",
  france: "FR",
  turkey: "TR",
  türkiye: "TR",
  turkiye: "TR",
  canada: "CA",
  australia: "AU",
  netherlands: "NL",
  belgium: "BE",
  spain: "ES",
  italy: "IT",
  ireland: "IE",
  sweden: "SE",
  norway: "NO",
  denmark: "DK",
  switzerland: "CH",
  austria: "AT",
  poland: "PL",
  portugal: "PT",
  "new zealand": "NZ",
  japan: "JP",
  singapore: "SG"
};

export function resolveCountryIso2(countryName: string | null): string | null {
  if (!countryName) return null;
  return COUNTRY_NAME_TO_ISO2[countryName.trim().toLowerCase()] ?? null;
}
