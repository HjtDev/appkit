import { describe, expect, it, vi } from "vitest";

import { runDuplicateCopyGuard } from "../../frontend/src/provider.js";

describe("runDuplicateCopyGuard — the dev-only duplicate-copy safeguard (§21)", () => {
  it("registers the marker silently on first call, warns naming the failure mode on second", () => {
    const registry: Record<symbol, boolean> = {};
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    runDuplicateCopyGuard(registry);
    expect(warn).not.toHaveBeenCalled();

    runDuplicateCopyGuard(registry);
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn.mock.calls[0]?.[0]).toContain("a second copy of appkit's module");
    expect(warn.mock.calls[0]?.[0]).toContain("npm ls appkit");

    warn.mockRestore();
  });

  it("is a no-op in a production NODE_ENV", () => {
    const original = process.env.NODE_ENV;
    process.env.NODE_ENV = "production";
    const registry: Record<symbol, boolean> = {};
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    runDuplicateCopyGuard(registry);
    runDuplicateCopyGuard(registry);
    expect(warn).not.toHaveBeenCalled();
    expect(Object.getOwnPropertySymbols(registry)).toHaveLength(0);

    process.env.NODE_ENV = original;
    warn.mockRestore();
  });
});
