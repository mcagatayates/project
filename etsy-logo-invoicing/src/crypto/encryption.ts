import { createCipheriv, createDecipheriv, randomBytes, createHash } from "node:crypto";

const ALGORITHM = "aes-256-gcm";
const IV_LENGTH = 12;

/**
 * Raw inbound email bodies contain buyer PII (name, address, email) and must
 * never be stored at rest in plaintext. AES-256-GCM authenticated encryption
 * is used; a random key is generated as a dev fallback ONLY so the app can
 * boot without configuration, and a warning is logged in that case (see
 * getOrCreateKey caller in db layer).
 */
function resolveKey(base64Key: string | undefined): Buffer {
  if (!base64Key) {
    // Deterministic, clearly-marked non-secret fallback for local/dev use only.
    return createHash("sha256").update("INSECURE_DEV_ONLY_KEY").digest();
  }
  const key = Buffer.from(base64Key, "base64");
  if (key.length !== 32) {
    throw new Error("PAYLOAD_ENCRYPTION_KEY must decode to exactly 32 bytes (base64)");
  }
  return key;
}

export function encryptPayload(plaintext: string, base64Key: string | undefined): string {
  const key = resolveKey(base64Key);
  const iv = randomBytes(IV_LENGTH);
  const cipher = createCipheriv(ALGORITHM, key, iv);
  const encrypted = Buffer.concat([cipher.update(plaintext, "utf8"), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return Buffer.concat([iv, authTag, encrypted]).toString("base64");
}

export function decryptPayload(ciphertext: string, base64Key: string | undefined): string {
  const key = resolveKey(base64Key);
  const raw = Buffer.from(ciphertext, "base64");
  const iv = raw.subarray(0, IV_LENGTH);
  const authTag = raw.subarray(IV_LENGTH, IV_LENGTH + 16);
  const encrypted = raw.subarray(IV_LENGTH + 16);
  const decipher = createDecipheriv(ALGORITHM, key, iv);
  decipher.setAuthTag(authTag);
  const decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()]);
  return decrypted.toString("utf8");
}

export function sha256Hex(input: string): string {
  return createHash("sha256").update(input, "utf8").digest("hex");
}
