import type { Order, Invoice } from "@prisma/client";

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function layout(title: string, body: string): string {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background: #0b0d12; color: #e6e8eb; }
  header { background: #14171f; padding: 16px 24px; border-bottom: 1px solid #262b36; }
  header a { color: #e6e8eb; text-decoration: none; font-weight: 600; }
  main { padding: 24px; max-width: 1100px; margin: 0 auto; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid #262b36; font-size: 14px; vertical-align: top; }
  th { color: #9aa4b2; font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .badge-manual { background: #4a2a12; color: #ffb066; }
  .badge-draft { background: #123a4a; color: #6fd0ff; }
  .badge-final { background: #103a1c; color: #6dffa0; }
  .badge-failed { background: #4a1212; color: #ff8080; }
  .badge-other { background: #2a2f3a; color: #c6cdd6; }
  form { display: inline; }
  button { background: #2a5bd7; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 13px; }
  button.secondary { background: #3a3f4a; }
  button:disabled { background: #23262e; color: #5b6270; cursor: not-allowed; opacity: 0.7; }
  pre { background: #14171f; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
  .issue { color: #ff8080; }
  .warn-banner { background: #4a2a12; color: #ffb066; padding: 10px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }
  a.link { color: #6fd0ff; }
</style>
</head>
<body>
<header><a href="/admin">Etsy &rarr; Logo Isbasi Invoicing — Admin</a></header>
<main>${body}</main>
</body>
</html>`;
}

function statusBadge(status: string): string {
  const cls =
    status === "MANUAL_REVIEW"
      ? "badge-manual"
      : status === "DRAFT_CREATED"
        ? "badge-draft"
        : status === "FINALIZED"
          ? "badge-final"
          : status.startsWith("FAILED")
            ? "badge-failed"
            : "badge-other";
  return `<span class="badge ${cls}">${escapeHtml(status)}</span>`;
}

export function renderOrderList(orders: (Order & { invoice: Invoice | null })[]): string {
  const rows = orders
    .map((o) => {
      const normalized = o.normalizedOrderJson as { buyerFullName?: string; orderTotal?: number; currency?: string } | null;
      return `<tr>
        <td><a class="link" href="/admin/orders/${o.id}">${escapeHtml(o.etsyOrderId)}</a></td>
        <td>${statusBadge(o.status)}</td>
        <td>${escapeHtml(normalized?.buyerFullName ?? "-")}</td>
        <td>${normalized?.orderTotal ?? "-"} ${escapeHtml(normalized?.currency ?? "")}</td>
        <td>${escapeHtml(o.invoice?.invoiceNumber ?? o.invoice?.logoInvoiceId ?? "-")}</td>
        <td>${escapeHtml(o.createdAt.toISOString())}</td>
      </tr>`;
    })
    .join("\n");

  const manualReviewCount = orders.filter((o) => o.status === "MANUAL_REVIEW").length;

  return layout(
    "Orders",
    `
    ${manualReviewCount > 0 ? `<div class="warn-banner">${manualReviewCount} order(s) awaiting manual review.</div>` : ""}
    <h1>Processed Orders</h1>
    <table>
      <thead><tr><th>Etsy Order</th><th>Status</th><th>Buyer</th><th>Total</th><th>Invoice</th><th>Detected</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="6">No orders yet.</td></tr>'}</tbody>
    </table>
  `
  );
}

export function renderOrderDetail(
  order: Order & { invoice: Invoice | null },
  processingAttempts: { operation: string; attemptNumber: number; status: string; errorCode: string | null; createdAt: Date }[]
): string {
  const validation = order.validationResult as { ok: boolean; issues: { code: string; message: string }[] } | null;
  const normalized = order.normalizedOrderJson;

  const issuesHtml = validation?.issues.length
    ? `<ul>${validation.issues.map((i) => `<li class="issue">${escapeHtml(i.code)}: ${escapeHtml(i.message)}</li>`).join("")}</ul>`
    : "<p>No validation issues.</p>";

  const attemptsRows = processingAttempts
    .map(
      (a) =>
        `<tr><td>${escapeHtml(a.operation)}</td><td>${a.attemptNumber}</td><td>${escapeHtml(a.status)}</td><td>${escapeHtml(a.errorCode ?? "-")}</td><td>${escapeHtml(a.createdAt.toISOString())}</td></tr>`
    )
    .join("\n");

  const canReprocess = !order.invoice;
  const canFinalize = Boolean(order.invoice && order.invoice.invoiceStatus === "DRAFT");

  return layout(
    `Order ${order.etsyOrderId}`,
    `
    <p><a class="link" href="/admin">&larr; Back to list</a></p>
    <h1>Order ${escapeHtml(order.etsyOrderId)} ${statusBadge(order.status)}</h1>

    <h2>Actions</h2>
    <form method="post" action="/admin/orders/${order.id}/reprocess">
      <button ${canReprocess ? "" : "disabled"} class="secondary">Reprocess (safe — will never create a 2nd invoice)</button>
    </form>
    <form method="post" action="/admin/orders/${order.id}/finalize">
      <button ${canFinalize ? "" : "disabled"}>Finalize draft invoice</button>
    </form>

    <h2>Extracted Order Data</h2>
    <pre>${escapeHtml(JSON.stringify(normalized, null, 2))}</pre>

    <h2>Validation</h2>
    ${issuesHtml}

    <h2>Invoice</h2>
    <pre>${escapeHtml(JSON.stringify(order.invoice, null, 2))}</pre>

    <h2>Processing Attempts</h2>
    <table>
      <thead><tr><th>Operation</th><th>Attempt</th><th>Status</th><th>Error Code</th><th>When</th></tr></thead>
      <tbody>${attemptsRows || '<tr><td colspan="5">No attempts recorded.</td></tr>'}</tbody>
    </table>
  `
  );
}
