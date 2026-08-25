"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useDemoConfig } from "../api/config.js";
import { DemoManager } from "../api/manager.js";
import { demoKeys } from "./useDemoItems.js";

// Bumps appkit.cache's SERVER-SIDE "demo_items" namespace — distinct from React Query's
// client-side cache, which the onSuccess below also invalidates so the UI reflects it
// immediately rather than waiting for the next natural refetch.
export function useInvalidateDemoCache() {
  const { client, basePath } = useDemoConfig();
  const manager = useMemo(() => new DemoManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => manager.invalidate(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: demoKeys.all });
    },
  });
}
