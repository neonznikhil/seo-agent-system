"use client";

import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { post } from "@/lib/api";

export default function WordPressCallbackPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const userLogin = searchParams.get("user_login");
  const password = searchParams.get("password");
  const siteUrl = searchParams.get("site_url");
  const state = searchParams.get("state");

  async function handleSave() {
    if (!userLogin || !password || !siteUrl || !state) {
      setError("Missing parameters from WordPress authorization");
      setLoading(false);
      return;
    }

    try {
      await post("/wordpress/save-connection", {
        username: userLogin,
        app_password: password,
        site_url: siteUrl,
        state: state || "",
      });
      router.push("/dashboard");
    } catch (err) {
      setError(err.message || "Failed to save WordPress connection");
      setLoading(false);
    }
  }

  useEffect(() => {
    handleSave();
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white shadow-md rounded-lg p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6 text-center">
          Connecting WordPress
        </h1>

        {loading && (
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-4" />
            <p className="text-gray-600">Saving your WordPress connection...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <p className="font-medium">Connection Error</p>
            <p className="text-sm mt-1">{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
