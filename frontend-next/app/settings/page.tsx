"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SettingsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/connectors");
  }, [router]);

  return (
    <div className="page-container active" style={{ padding: "40px", textAlign: "center" }}>
      <p className="mono-font" style={{ fontSize: "12px", color: "var(--muted)" }}>
        Redirecting to Connectors...
      </p>
    </div>
  );
}
