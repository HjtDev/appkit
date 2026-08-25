import { describe, expect, it } from "vitest";

import { mediaUrl } from "../../frontend/src/media.js";

describe("mediaUrl", () => {
  it("returns null for null", () => {
    expect(mediaUrl(null, "https://api.example.com")).toBe(null);
  });

  it("returns null for undefined", () => {
    expect(mediaUrl(undefined, "https://api.example.com")).toBe(null);
  });

  it("returns null for an empty string", () => {
    expect(mediaUrl("", "https://api.example.com")).toBe(null);
  });

  it("prefixes a relative path with baseUrl", () => {
    expect(mediaUrl("/media/avatar.png", "https://api.example.com")).toBe(
      "https://api.example.com/media/avatar.png",
    );
  });

  it("adds a leading slash if the value lacks one", () => {
    expect(mediaUrl("media/avatar.png", "https://api.example.com")).toBe(
      "https://api.example.com/media/avatar.png",
    );
  });

  it("strips a trailing slash on baseUrl so the join never double-slashes", () => {
    expect(mediaUrl("/media/avatar.png", "https://api.example.com/")).toBe(
      "https://api.example.com/media/avatar.png",
    );
  });

  it("passes an already-absolute URL through unchanged, never double-prefixed", () => {
    expect(mediaUrl("https://cdn.example.com/x.png", "https://api.example.com")).toBe(
      "https://cdn.example.com/x.png",
    );
  });

  it("treats a protocol-relative URL as not absolute, and prefixes it", () => {
    expect(mediaUrl("//cdn.example.com/x.png", "https://api.example.com")).toBe(
      "https://api.example.com//cdn.example.com/x.png",
    );
  });
});
