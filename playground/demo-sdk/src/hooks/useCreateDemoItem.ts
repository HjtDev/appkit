"use client";

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useDemoConfig } from "../api/config.js";
import { DemoManager } from "../api/manager.js";
import { demoKeys } from "./useDemoItems.js";
import type { CreateDemoItemPayload } from "../types.js";

export function useCreateDemoItem() {
  const { client, basePath } = useDemoConfig();
  const manager = useMemo(() => new DemoManager(client, basePath), [client, basePath]);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: CreateDemoItemPayload) => manager.create(payload),
    onSuccess: () => {
      // Invalidate appkit's own server-side cache namespace too — the two caches (React
      // Query's client-side cache and appkit.cache's server-side one) are independent, and a
      // mutation hook only owns the first. See playground/frontend/app/page.tsx for the second.
      void queryClient.invalidateQueries({ queryKey: demoKeys.all });
    },
  });
}
