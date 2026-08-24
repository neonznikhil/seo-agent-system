"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function RoiAttributionPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/");
  }, [router]);

  return (
    <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
      <p style={{ color: "var(--muted)" }}>Redirecting to Dashboard...</p>
    </div>
  );
}
