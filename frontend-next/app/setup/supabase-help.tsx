"use client";

export default function SupabaseHelp() {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
      <h3 className="text-sm font-semibold text-blue-900 mb-2">
        Where to find your keys
      </h3>
      <ol className="text-sm text-blue-800 space-y-1 list-decimal list-inside">
        <li>Go to Supabase Dashboard &gt; Settings &gt; API</li>
        <li>Copy "Project URL" (https://xxxx.supabase.co)</li>
        <li>Copy "anon public" key (starts with eyJ...)</li>
        <li>Copy "service_role" key (starts with eyJ...) - keep this secret!</li>
        <li>Go to Database &gt; Password to get your DB password</li>
      </ol>
    </div>
  );
}
