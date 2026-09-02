import { NextResponse } from "next/server";
import { articlesStore } from "../../articles-store";

export async function GET() {
  return NextResponse.json(articlesStore);
}
