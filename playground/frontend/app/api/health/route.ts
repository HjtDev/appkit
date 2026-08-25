import { NextResponse } from "next/server";

// Deliberately never calls the backend — a down API must not take the frontend out of
// rotation, same reasoning as base-scaffold's own /api/health route.
export function GET() {
  return NextResponse.json({ status: "ok" });
}
