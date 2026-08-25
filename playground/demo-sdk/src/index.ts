// Public surface — the manager and api/config.ts are NEVER exported, per
// docs/APP-DESIGN.md:1516-1536's SDK-authoring convention. Only hooks, the query-key factory
// (so a host can invalidate), and types.

export { useDemoItems, demoKeys } from "./hooks/useDemoItems.js";
export { useCreateDemoItem } from "./hooks/useCreateDemoItem.js";
export { useInvalidateDemoCache } from "./hooks/useInvalidateDemoCache.js";
export type { DemoItem, DemoItemPage, CreateDemoItemPayload } from "./types.js";
