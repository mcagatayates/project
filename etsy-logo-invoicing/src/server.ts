import Fastify, { type FastifyInstance } from "fastify";
import type { PrismaClient } from "@prisma/client";
import type { Env } from "./config/env.js";
import type { Logger } from "./logging/logger.js";
import { registerAdminPanel, type AdminPanelDeps } from "./admin-panel/routes.js";

export interface BuildServerDeps {
  env: Env;
  logger: Logger;
  prisma: PrismaClient;
  adminPanelDeps: AdminPanelDeps;
}

export async function buildServer(deps: BuildServerDeps): Promise<FastifyInstance> {
  const app = Fastify({ logger: { level: deps.env.LOG_LEVEL } });

  app.get("/health", async (_req, reply) => {
    try {
      await deps.prisma.$queryRaw`SELECT 1`;
      reply.send({ status: "ok", database: "connected" });
    } catch (err) {
      reply.code(503).send({ status: "error", database: "unreachable", error: (err as Error).message });
    }
  });

  await registerAdminPanel(app, deps.adminPanelDeps);

  return app;
}
