export interface RetryOptions {
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
  isRetryable: (err: unknown) => boolean;
  /** Called between attempts, after a retryable failure and before sleeping. */
  onRetryableFailure?: (attempt: number, err: unknown) => Promise<void> | void;
  sleep?: (ms: number) => Promise<void>;
}

const defaultSleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function computeBackoffDelay(attempt: number, baseDelayMs: number, maxDelayMs: number): number {
  const exp = baseDelayMs * 2 ** (attempt - 1);
  return Math.min(exp, maxDelayMs);
}

/**
 * Generic exponential-backoff retry loop for network/timeout/429/5xx style
 * failures. Validation (4xx) errors should be classified as non-retryable
 * by `isRetryable` so they fail fast instead of being retried.
 */
export async function withRetry<T>(fn: (attempt: number) => Promise<T>, options: RetryOptions): Promise<T> {
  const sleep = options.sleep ?? defaultSleep;
  let attempt = 0;
  let lastError: unknown;

  while (attempt < options.maxAttempts) {
    attempt += 1;
    try {
      return await fn(attempt);
    } catch (err) {
      lastError = err;
      if (!options.isRetryable(err) || attempt >= options.maxAttempts) {
        throw err;
      }
      if (options.onRetryableFailure) {
        await options.onRetryableFailure(attempt, err);
      }
      const delay = computeBackoffDelay(attempt, options.baseDelayMs, options.maxDelayMs);
      await sleep(delay);
    }
  }
  throw lastError;
}
