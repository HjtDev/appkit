"use client";

import { useState } from "react";
import { useDemoItems, useCreateDemoItem, useInvalidateDemoCache } from "demo-sdk";
import { isApiError } from "@hjtdev/appkit";

export default function HomeClient() {
  const items = useDemoItems();
  const createItem = useCreateDemoItem();
  const invalidateCache = useInvalidateDemoCache();
  const [name, setName] = useState("");

  return (
    <main>
      <h1>Demo items (useDemoItems / useCreateDemoItem)</h1>
      <p>
        Exercises appkit.mixins.CachedListMixin + appkit.pagination.DefaultPagination server-side,
        and demo-sdk&apos;s manager/hook binding over useApiClient(&quot;demo&quot;,
        &quot;/api/v1/demo&quot;) client-side.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) createItem.mutate({ name });
          setName("");
        }}
      >
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="item name" />
        <button type="submit" disabled={createItem.isPending}>
          Create
        </button>
        <button type="button" onClick={() => invalidateCache.mutate()}>
          Invalidate server cache
        </button>
      </form>

      {items.isLoading && <p>Loading…</p>}
      {items.isError && (
        <p style={{ color: "crimson" }}>
          Error: {isApiError(items.error) ? `${items.error.code} (${items.error.status})` : "unknown"}
        </p>
      )}
      {items.data && (
        <>
          <p>
            count={items.data.count}, next={items.data.next ?? "null"}, previous=
            {items.data.previous ?? "null"}
          </p>
          <ul>
            {items.data.results.map((item) => (
              <li key={item.id}>
                #{item.id} {item.name} — {item.created_at}
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}
