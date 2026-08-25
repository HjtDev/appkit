import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { setupServer } from "msw/node";

// Mock the HTTP layer, never a live backend, and fail loudly on any request nobody set up a
// handler for rather than silently letting it through — mirrors the base-scaffold's own MSW
// setup (../base-scaffold/frontend/tests/setup.ts), which every installed app's own test suite
// is meant to copy (APP-DESIGN.md §7.7).
export const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
