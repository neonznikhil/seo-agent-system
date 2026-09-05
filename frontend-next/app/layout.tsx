import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { Topbar } from "@/components/Topbar";

export const metadata: Metadata = {
  title: "RANKFORGE - Autonomous SEO Agent System",
  description: "10-Phase Autonomous SEO Content Engine & Rank Intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DotGothic16&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              window.toggleFAQItem = function(id) {
                var item = document.getElementById('rf-faq-item-' + id);
                var content = document.getElementById('faq-content-' + id);
                var arrow = document.getElementById('arrow-' + id);
                var iconWrap = document.getElementById('arrow-wrap-' + id);
                var badge = document.getElementById('rf-badge-' + id);
                var title = document.getElementById('rf-title-' + id);
                var bar = document.getElementById('rf-bar-' + id);
                if (!content) return;
                var isOpen = content.style.maxHeight && content.style.maxHeight !== '0px';
                if (isOpen) {
                  content.style.maxHeight = '0px';
                  content.style.opacity = '0';
                  if (item) {
                    item.classList.remove('rf-open');
                    item.style.borderColor = '#e2e8f0';
                    item.style.boxShadow = '0 1px 3px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.02)';
                    item.style.background = '#ffffff';
                  }
                  if (arrow) {
                    arrow.style.color = '#64748b';
                  }
                  if (iconWrap) {
                    iconWrap.style.background = '#f8fafc';
                    iconWrap.style.borderColor = '#e2e8f0';
                    iconWrap.style.transform = 'rotate(0deg)';
                    iconWrap.style.boxShadow = 'none';
                  }
                  if (badge) {
                    badge.style.background = 'linear-gradient(135deg,#f1f5f9 0%,#e2e8f0 100%)';
                    badge.style.color = '#475569';
                    badge.style.transform = 'scale(1)';
                    badge.style.boxShadow = 'inset 0 1px 0 rgba(255,255,255,0.5)';
                  }
                  if (title) {
                    title.style.color = '#0f172a';
                    title.style.fontWeight = '600';
                  }
                  if (bar) {
                    bar.style.opacity = '0';
                  }
                } else {
                  content.style.maxHeight = (content.scrollHeight + 40) + 'px';
                  content.style.opacity = '1';
                  if (item) {
                    item.classList.add('rf-open');
                    item.style.borderColor = '#0d9488';
                    item.style.boxShadow = '0 16px 40px -8px rgba(13, 148, 136, 0.2), 0 6px 16px -4px rgba(13, 148, 136, 0.08)';
                    item.style.background = 'linear-gradient(180deg,#ffffff 0%,#f0fdfa 100%)';
                  }
                  if (arrow) {
                    arrow.style.color = '#ffffff';
                  }
                  if (iconWrap) {
                    iconWrap.style.background = 'linear-gradient(135deg,#0d9488 0%,#14b8a6 100%)';
                    iconWrap.style.borderColor = '#0d9488';
                    iconWrap.style.transform = 'rotate(180deg)';
                    iconWrap.style.boxShadow = '0 4px 12px rgba(13, 148, 136, 0.3)';
                  }
                  if (badge) {
                    badge.style.background = 'linear-gradient(135deg,#0d9488 0%,#14b8a6 100%)';
                    badge.style.color = '#ffffff';
                    badge.style.transform = 'scale(1.05)';
                    badge.style.boxShadow = '0 4px 12px rgba(13, 148, 136, 0.35), inset 0 1px 0 rgba(255,255,255,0.2)';
                  }
                  if (title) {
                    title.style.color = '#0f766e';
                    title.style.fontWeight = '700';
                  }
                  if (bar) {
                    bar.style.opacity = '1';
                  }
                }
              };
              if (typeof document !== 'undefined') {
                document.addEventListener('click', function(e) {
                  var header = e.target.closest ? e.target.closest('.rf-faq-header') : null;
                  if (header) {
                    var card = header.closest('.rf-faq-card');
                    if (card && card.id) {
                      var m = card.id.match(/rf-faq-item-(\\d+)/);
                      if (m && m[1]) {
                        window.toggleFAQItem(parseInt(m[1], 10));
                      }
                    }
                  }
                });
              }
            `,
          }}
        />
      </head>
      <body>
        <div className="app-shell">
          <Sidebar />
          <div className="main">
            <Topbar />
            <div className="page-wrap">{children}</div>
          </div>
        </div>
      </body>
    </html>
  );
}
