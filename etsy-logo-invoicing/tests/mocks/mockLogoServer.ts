import Fastify, { type FastifyInstance } from "fastify";
import { randomUUID } from "node:crypto";

/**
 * Mock Logo Isbasi HTTP server used ONLY by tests.
 *
 * IMPORTANT: this exposes a contract *this project invented for its own
 * test harness* (POST /invoices/draft, GET /invoices/by-reference/:ref,
 * POST /invoices/:id/finalize). It is NOT a reproduction of Logo Isbasi's
 * real API — docs/logo-isbasi-api/ was empty at implementation time, so
 * the real contract is unknown (see RealLogoIsbasiClient.ts). This server
 * exists so integration tests can exercise retry/backoff/idempotency
 * logic against real HTTP timeouts and status codes rather than purely
 * in-memory simulation (see MockLogoClient for the in-memory equivalent
 * used in unit tests and as the default runtime client).
 */

export type InjectedFault = "TIMEOUT" | "RATE_LIMIT" | "SERVER_ERROR" | "VALIDATION_ERROR" | null;

export interface MockLogoInvoice {
  logoInvoiceId: string;
  externalReference: string;
  invoiceNumber: string | null;
  status: "DRAFT" | "FINALIZED";
}

export interface MockLogoServerHandle {
  app: FastifyInstance;
  invoices: Map<string, MockLogoInvoice>;
  injectFault: (fault: InjectedFault) => void;
  draftCallCount: () => number;
}

export function buildMockLogoServer(): MockLogoServerHandle {
  const app = Fastify({ logger: false });
  const invoices = new Map<string, MockLogoInvoice>();
  let pendingFault: InjectedFault = null;
  let draftCalls = 0;

  app.get("/health", async () => ({ status: "ok" }));

  app.post<{ Body: { externalReference: string } }>("/invoices/draft", async (req, reply) => {
    draftCalls += 1;
    const { externalReference } = req.body;
    const fault = pendingFault;
    pendingFault = null;

    if (fault === "TIMEOUT") {
      // Simulate Logo having actually persisted the invoice server-side
      // even though the client will observe a timeout.
      invoices.set(externalReference, {
        logoInvoiceId: randomUUID(),
        externalReference,
        invoiceNumber: null,
        status: "DRAFT"
      });
      // Never respond within the client's timeout window.
      await new Promise(() => {
        /* intentionally hangs */
      });
      return;
    }
    if (fault === "RATE_LIMIT") {
      reply.code(429).send({ error: "rate_limited" });
      return;
    }
    if (fault === "SERVER_ERROR") {
      reply.code(503).send({ error: "server_error" });
      return;
    }
    if (fault === "VALIDATION_ERROR") {
      reply.code(400).send({ error: "validation_error", details: "simulated" });
      return;
    }

    const existing = invoices.get(externalReference);
    if (existing) {
      reply.code(200).send(existing);
      return;
    }
    const created: MockLogoInvoice = {
      logoInvoiceId: randomUUID(),
      externalReference,
      invoiceNumber: null,
      status: "DRAFT"
    };
    invoices.set(externalReference, created);
    reply.code(201).send(created);
  });

  app.get<{ Params: { ref: string } }>("/invoices/by-reference/:ref", async (req, reply) => {
    const invoice = invoices.get(req.params.ref);
    if (!invoice) {
      reply.code(404).send({ error: "not_found" });
      return;
    }
    reply.code(200).send(invoice);
  });

  app.post<{ Params: { id: string } }>("/invoices/:id/finalize", async (req, reply) => {
    const found = [...invoices.values()].find((i) => i.logoInvoiceId === req.params.id);
    if (!found) {
      reply.code(404).send({ error: "not_found" });
      return;
    }
    found.status = "FINALIZED";
    found.invoiceNumber = found.invoiceNumber ?? `INV-${found.logoInvoiceId.slice(0, 8)}`;
    reply.code(200).send(found);
  });

  return {
    app,
    invoices,
    injectFault: (fault) => {
      pendingFault = fault;
    },
    draftCallCount: () => draftCalls
  };
}
