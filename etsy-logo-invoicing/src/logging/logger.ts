import pino from "pino";

const REDACT_PATHS = [
  "req.headers.authorization",
  "*.apiKey",
  "*.api_key",
  "*.token",
  "*.accessToken",
  "*.refreshToken",
  "*.secret",
  "*.password",
  "*.clientSecret",
  "*.sharedSecret",
  "*.email",
  "*.buyerEmail",
  "*.addressLine1",
  "*.addressLine2",
  "*.buyerName",
  "*.recipientName"
];

export function createLogger(level: string, pretty = process.env.NODE_ENV !== "production") {
  return pino({
    level,
    redact: {
      paths: REDACT_PATHS,
      censor: "[REDACTED]"
    },
    transport: pretty
      ? {
          target: "pino-pretty",
          options: { colorize: true, translateTime: "SYS:standard" }
        }
      : undefined
  });
}

export type Logger = ReturnType<typeof createLogger>;
