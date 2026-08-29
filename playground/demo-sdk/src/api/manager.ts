// Instance-based manager — the ONLY place a raw HTTP call happens in this SDK
// (docs/APP-DESIGN.md:1495-1512). Never exported from src/index.ts.

import type { HttpClient } from "@hjtdev/appkit";
import type { CreateDemoItemPayload, DemoItem, DemoItemPage } from "../types.js";

export class DemoManager {
  constructor(
    private readonly client: HttpClient,
    private readonly basePath: string,
  ) {}

  list(): Promise<DemoItemPage> {
    return this.client.get<DemoItemPage>(`${this.basePath}/items/`);
  }

  create(payload: CreateDemoItemPayload): Promise<DemoItem> {
    return this.client.post<DemoItem>(`${this.basePath}/items/`, payload);
  }

  invalidate(): Promise<{ namespace: string; version: number }> {
    return this.client.post<{ namespace: string; version: number }>(
      `${this.basePath}/items/invalidate/`,
    );
  }
}
