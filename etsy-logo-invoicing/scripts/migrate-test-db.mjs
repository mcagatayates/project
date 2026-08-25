import { config } from "dotenv";
import { execSync } from "node:child_process";

config({ path: ".env.test" });

execSync("npx prisma migrate deploy", { stdio: "inherit", env: process.env });
