const ENTITY_MAP: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#39;": "'",
  "&apos;": "'",
  "&nbsp;": " "
};

function decodeEntities(input: string): string {
  return input.replace(/&amp;|&lt;|&gt;|&quot;|&#39;|&apos;|&nbsp;/g, (m) => ENTITY_MAP[m] ?? m);
}

/**
 * Converts an HTML email body into plain-text-like output so the same
 * deterministic label-based parser can run against both HTML and
 * plain-text Etsy emails. Deliberately simple (no DOM dependency): strips
 * script/style, converts block-level tags to newlines, strips remaining
 * tags, decodes common entities, collapses whitespace.
 */
export function htmlToText(html: string): string {
  let out = html;
  out = out.replace(/<script[\s\S]*?<\/script>/gi, "");
  out = out.replace(/<style[\s\S]*?<\/style>/gi, "");
  out = out.replace(/<!--[\s\S]*?-->/g, "");
  out = out.replace(/<(br|\/p|\/div|\/tr|\/li|\/h[1-6])\s*\/?>/gi, "\n");
  out = out.replace(/<(p|div|tr|li|h[1-6])[^>]*>/gi, "\n");
  out = out.replace(/<td[^>]*>/gi, " ");
  out = out.replace(/<[^>]+>/g, "");
  out = decodeEntities(out);
  out = out
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trim())
    .filter((line, idx, arr) => !(line === "" && arr[idx - 1] === ""))
    .join("\n");
  return out.trim();
}
