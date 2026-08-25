"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDemoConfig } from "../api/config.js";
import { DemoManager } from "../api/manager.js";

// Exported — a host needs this to invalidate the right query keys itself
// (docs/APP-DESIGN.md:1516-1536).
export const demoKeys = {
  all: ["demo"] as const,
  list: () => [...demoKeys.all, "list"] as const,
};

export function useDemoItems() {
  const { client, basePath } = useDemoConfig();
  const manager = useMemo(() => new DemoManager(client, basePath), [client, basePath]);
  return useQuery({ queryKey: demoKeys.list(), queryFn: () => manager.list() });
}
