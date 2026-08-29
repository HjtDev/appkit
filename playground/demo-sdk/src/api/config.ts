// Internal — never exported from src/index.ts. Every real app SDK's api/config.ts follows this
// exact shape (docs/APP-DESIGN.md:1470-1473): a thin call to appkit's useApiClient(key,
// defaultBasePath), never anything host-specific.
"use client";

import { useApiClient } from "@hjtdev/appkit";

export const useDemoConfig = () => useApiClient("demo", "/api/v1/demo");
