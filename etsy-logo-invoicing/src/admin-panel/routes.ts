import type { FastifyInstance, FastifyReply, FastifyRequest } from "fastify";
import fastifyBasicAuth from "@fastify/basic-auth";

type BasicAuthDecorated = FastifyInstance & {
  basicAuth: (req: FastifyRequest, reply: FastifyReply, done: (err?: Error) => void) => void;
};
import type { Env } from "../config/env.js";
import type { OrderRepository } from "../db/repositories/orderRepository.js";
import type { InvoiceRepository } from "../db/repositories/invoiceRepository.js";
import type { ProcessingAttemptRepository } from "../db/repositories/processingAttemptRepository.js";
import type { InvoiceService } from "../invoice-service/InvoiceService.js";
import { renderOrderDetail, renderOrderList } from "./views.js";

export interface AdminPanelDeps {
  env: Env;
  orderRepository: OrderRepository;
  invoiceRepository: InvoiceRepository;
  processingAttemptRepository: ProcessingAttemptRepository;
  invoiceService: InvoiceService;
}

export async function registerAdminPanel(app: FastifyInstance, deps: AdminPanelDeps): Promise<void> {
  const { env, orderRepository, invoiceRepository, processingAttemptRepository, invoiceService } = deps;

  await app.register(
    async (adminApp) => {
      await adminApp.register(fastifyBasicAuth, {
        validate: async (username, password) => {
          const ok = username === env.ADMIN_USERNAME && password === env.ADMIN_PASSWORD;
          if (!ok) throw new Error("Unauthorized");
        },
        authenticate: true
      });
      const authedApp = adminApp as BasicAuthDecorated;
      adminApp.addHook("onRequest", (req, reply, done) => authedApp.basicAuth(req, reply, done));

      adminApp.get("/", async (_req, reply) => {
        const orders = await orderRepository.listAll(200);
        const withInvoices = await Promise.all(
          orders.map(async (o) => ({ ...o, invoice: await invoiceRepository.findByOrderId(o.id) }))
        );
        reply.type("text/html").send(renderOrderList(withInvoices));
      });

      adminApp.get<{ Params: { id: string } }>("/orders/:id", async (req, reply) => {
        const order = await orderRepository.findById(req.params.id);
        if (!order) return reply.code(404).send("Order not found");
        const invoice = await invoiceRepository.findByOrderId(order.id);
        const attempts = await processingAttemptRepository.listForOrder(order.id);
        reply.type("text/html").send(renderOrderDetail({ ...order, invoice }, attempts));
      });

      adminApp.post<{ Params: { id: string } }>("/orders/:id/reprocess", async (req, reply) => {
        await invoiceService.reprocessOrder(req.params.id);
        reply.redirect(`/admin/orders/${req.params.id}`);
      });

      adminApp.post<{ Params: { id: string } }>("/orders/:id/finalize", async (req, reply) => {
        try {
          await invoiceService.finalizeInvoiceForOrder(req.params.id);
        } catch (err) {
          reply.code(400);
          reply
            .type("text/html")
            .send(`<p>Finalize failed: ${(err as Error).message}</p><a href="/admin/orders/${req.params.id}">Back</a>`);
          return;
        }
        reply.redirect(`/admin/orders/${req.params.id}`);
      });
    },
    { prefix: "/admin" }
  );
}
