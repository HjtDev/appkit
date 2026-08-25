// Verbatim from README.md:230-258 ("Usage — mounting the shared provider"), adapted only in
// the two host-specific import lines the README itself marks as host-owned
// ("@/lib/api-client", "@/lib/auth") — nothing about ApiClientProvider/makeQueryClient/
// QueryClientProvider usage below was changed.
"use client";

import { useState, useMemo } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { ApiClientProvider, makeQueryClient } from "appkit";
import { apiClient } from "@/lib/api-client";
import { getAuthHeaders } from "@/lib/auth"; // host's own — appkit knows nothing about it

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(() => makeQueryClient());
  const headerSources = useMemo(() => [getAuthHeaders], []); // stable reference — see below

  return (
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider
        client={apiClient}
        headerSources={headerSources}
        basePaths={{
          demo: "/api/v1/demo",
        }}
      >
        {children}
      </ApiClientProvider>
    </QueryClientProvider>
  );
}
