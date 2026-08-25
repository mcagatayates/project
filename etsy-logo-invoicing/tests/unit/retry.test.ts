import { describe, expect, it, vi } from "vitest";
import { withRetry, computeBackoffDelay } from "../../src/retry/retry.js";

describe("retry", () => {
  it("computes exponential backoff capped at maxDelayMs", () => {
    expect(computeBackoffDelay(1, 1000, 60000)).toBe(1000);
    expect(computeBackoffDelay(2, 1000, 60000)).toBe(2000);
    expect(computeBackoffDelay(3, 1000, 60000)).toBe(4000);
    expect(computeBackoffDelay(10, 1000, 60000)).toBe(60000);
  });

  it("retries retryable errors up to maxAttempts and then throws", async () => {
    let calls = 0;
    const err = new Error("boom");
    await expect(
      withRetry(
        async () => {
          calls += 1;
          throw err;
        },
        { maxAttempts: 3, baseDelayMs: 1, maxDelayMs: 5, isRetryable: () => true, sleep: async () => {} }
      )
    ).rejects.toBe(err);
    expect(calls).toBe(3);
  });

  it("does not retry non-retryable errors", async () => {
    let calls = 0;
    const err = new Error("validation");
    await expect(
      withRetry(
        async () => {
          calls += 1;
          throw err;
        },
        { maxAttempts: 5, baseDelayMs: 1, maxDelayMs: 5, isRetryable: () => false, sleep: async () => {} }
      )
    ).rejects.toBe(err);
    expect(calls).toBe(1);
  });

  it("returns the result once a retry succeeds", async () => {
    let calls = 0;
    const result = await withRetry(
      async () => {
        calls += 1;
        if (calls < 2) throw new Error("transient");
        return "ok";
      },
      { maxAttempts: 5, baseDelayMs: 1, maxDelayMs: 5, isRetryable: () => true, sleep: async () => {} }
    );
    expect(result).toBe("ok");
    expect(calls).toBe(2);
  });

  it("invokes onRetryableFailure between attempts", async () => {
    const onRetryableFailure = vi.fn();
    let calls = 0;
    await withRetry(
      async () => {
        calls += 1;
        if (calls < 2) throw new Error("transient");
        return "ok";
      },
      { maxAttempts: 5, baseDelayMs: 1, maxDelayMs: 5, isRetryable: () => true, sleep: async () => {}, onRetryableFailure }
    );
    expect(onRetryableFailure).toHaveBeenCalledTimes(1);
  });
});
