export interface DemoItem {
  id: number;
  name: string;
  created_at: string;
}

export interface DemoItemPage {
  count: number;
  next: string | null;
  previous: string | null;
  results: DemoItem[];
}

export interface CreateDemoItemPayload {
  name: string;
}
