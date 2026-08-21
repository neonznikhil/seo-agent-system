"use client";

import { useState } from "react";

interface ApprovalCardProps {
  id: string;
  title: string;
  content?: string;
  type?: "page" | "blog" | "homepage";
  url?: string;
  status?: string | null;
  issueType?: string;
  oldValue?: string;
  newValue?: string;
  onApprove?: (confirmHomepage?: boolean) => void;
  onReject?: () => void;
  lastFixDate?: string;
}

export function ApprovalCard({
  id,
  title,
  content,
  type = "page",
  url = "",
  status = "pending",
  issueType = "",
  oldValue,
  newValue,
  onApprove,
  onReject,
  lastFixDate,
}: ApprovalCardProps) {
  const [localStatus, setLocalStatus] = useState(status);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showHompageConfirm, setShowHompageConfirm] = useState(false);
  const [showPublishConfirm, setShowPublishConfirm] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [homepageConfirmText, setHomepageConfirmText] = useState("");
  const [loading, setLoading] = useState(false);

  const isHomepage = url === "/" || url === "/index" || url?.endsWith("/index.html");

  const handleApprove = () => {
    if (type === "blog") {
      setShowPublishConfirm(true);
      return;
    }
    if (isHomepage) {
      setShowHompageConfirm(true);
      return;
    }
    setLocalStatus("approved");
    setShowConfirm(false);
    onApprove?.();
  };

  const handleHomepageConfirm = () => {
    if (homepageConfirmText === "UPDATE HOMEPAGE") {
      setShowHompageConfirm(false);
      setLocalStatus("approved");
      onApprove?.(true);
    }
  };

  const handlePublishConfirm = () => {
    setShowPublishConfirm(false);
    setLoading(true);
    setLocalStatus("approved");
    onApprove?.();
  };

  const handleRejectClick = () => {
    setShowConfirm(true);
  };

  const handleReject = () => {
    setLocalStatus("rejected");
    setShowConfirm(false);
    setRejectReason("");
    onReject?.();
  };

  if (!title && !content) return null;

  const isDeleteAction = issueType === "delete_page";

  return (
    <>
      <div className="bg-stone border border-ink p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="w-2 h-2 bg-accent rounded-full" />
              <div className="text-[11px] text-muted uppercase tracking-wider mono-font">
                {(localStatus || "pending").toUpperCase()}
              </div>
            </div>
            <h3 className="text-lg font-bold uppercase mb-2">{title}</h3>
            
            {url && (
              <div className="text-[10px] text-muted mono-font mb-2">
                URL: <span className="text-ink">{url}</span>
              </div>
            )}
            
            {oldValue && newValue && (
              <div className="border border-ink p-2 mb-2">
                <div className="text-[10px] text-muted mono-font mb-1">CHANGE</div>
                <div className="text-sm">
                  <span className="text-muted">{oldValue.slice(0, 50)}...</span>
                  <span className="mx-2">→</span>
                  <span className="text-accent font-bold mono-font">{newValue.slice(0, 50)}...</span>
                </div>
              </div>
            )}
            
            {content && !oldValue && !newValue && (
              <div className="border-l-2 border-line pl-4 text-sm text-muted mb-4">
                {content.slice(0, 200)}...
              </div>
            )}
          </div>
        </div>
        
        {localStatus === "pending" && !isDeleteAction && (
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleApprove}
              disabled={loading}
              className={`flex items-center gap-2 px-4 py-2 text-[11px] uppercase tracking-widest mono-font ${
                isHomepage 
                  ? "bg-red-800 hover:bg-red-900 text-white" 
                  : "bg-ink text-paper"
              } ${loading ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <span className="w-2 h-2 bg-accent" />
              {isHomepage ? "UPDATE HOMEPAGE" : "APPROVE"}
            </button>
            <button 
              onClick={handleRejectClick}
              disabled={loading}
              className={`px-4 py-2 border border-ink text-[11px] uppercase tracking-widest mono-font pill ${
                loading ? "opacity-50 cursor-not-allowed" : ""
              }`}
            >
              Reject
            </button>
          </div>
        )}
        
        {isDeleteAction && (
          <div className="border border-ink bg-paper p-3 mb-2">
            <div className="text-[10px] text-muted mono-font mb-1">⚠️ DELETE BLOCKED</div>
            <div className="text-sm text-ink mono-font">
              DELETE BLOCKED: Agents never allowed to delete. Contact admin.
            </div>
          </div>
        )}
      </div>

      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-paper border border-ink p-4 w-80">
            <div className="text-[11px] text-muted uppercase mono-font mb-2">REJECT?</div>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="w-full h-20 border border-ink bg-stone p-2 text-[11px] mono-font mb-2"
              placeholder="Reason (optional)..."
            />
            <div className="flex gap-2">
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 px-3 py-1 border border-ink text-[11px] mono-font pill"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                className="flex-1 px-3 py-1 border border-ink bg-ink text-paper text-[11px] mono-font"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {showHompageConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-stone border border-ink p-4 w-96">
            <div className="text-lg font-bold text-ink dot-font mb-2">⚠️ CRITICAL CONFIRM</div>
            <div className="text-sm text-muted mono-font mb-3">
              You are updating HOMEPAGE. This is sacred.
            </div>
            {lastFixDate && (
              <div className="text-xs text-muted mono-font mb-3">
                Last fix: {lastFixDate} - 14-day cooldown may apply
              </div>
            )}
            <div className="mb-3">
              <span className="text-ink">Type to confirm: </span>
              <input
                type="text"
                value={homepageConfirmText}
                onChange={(e) => setHomepageConfirmText(e.target.value)}
                className="border border-ink bg-paper px-2 py-1 text-[11px] mono-font w-full"
                placeholder="UPDATE HOMEPAGE"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowHompageConfirm(false)}
                className="flex-1 px-3 py-1 border border-ink text-[11px] mono-font pill"
              >
                Cancel
              </button>
              <button
                onClick={handleHomepageConfirm}
                disabled={homepageConfirmText !== "UPDATE HOMEPAGE"}
                className={`flex-1 px-3 py-1 text-[11px] mono-font ${
                  homepageConfirmText === "UPDATE HOMEPAGE" 
                    ? "bg-ink text-paper" 
                    : "border border-ink border-dashed text-muted"
                }`}
              >
                Confirm Update
              </button>
            </div>
          </div>
        </div>
      )}

      {showPublishConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-stone border border-ink p-4 w-96">
            <div className="text-lg font-bold text-ink dot-font mb-2">⚠️ PUBLISH TO WORDPRESS</div>
            <div className="text-sm text-muted mono-font mb-3">
              Publish blog: <span className="text-ink font-bold">{title}</span>
            </div>
            <div className="text-xs text-muted mono-font mb-3">
              This will be live at: <span className="text-accent">{url || 'https://example.com/blog/...'}</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowPublishConfirm(false)}
                className="flex-1 px-3 py-1 border border-ink text-[11px] mono-font pill"
              >
                Cancel
              </button>
              <button
                onClick={handlePublishConfirm}
                disabled={loading}
                className="flex-1 px-3 py-1 bg-ink text-paper text-[11px] mono-font"
              >
                Publish
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}