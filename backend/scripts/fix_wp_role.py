"""
Fix WordPress 401 rest_cannot_create - Editor Role Instructions for Maruf test site https://accident.innovatcs.com
Problem: GET /wp-json/wp/v2/posts?per_page=1 200 READ works, POST /wp-json/wp/v2/posts 401 rest_cannot_create = WP user does NOT have capability publish_posts - current role Subscriber/Contributor needs Author/Editor.

Solution verified: publish_post pre-check GET /wp-json/wp/v2/users/me auth -> check roles array -> if subscriber/contributor -> return clear error + dashboard yellow banner.

Run: python backend/scripts/fix_wp_role.py --check --site https://accident.innovatcs.com --user admin --password "xxxx xxxx xxxx xxxx"
Or: python backend/scripts/fix_wp_role.py --instructions
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path
# Ensure UTF-8 for Windows console (emoji ✅)
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

INSTRUCTIONS = """
================================================================
FIX WORDPRESS 401 rest_cannot_create - EDITOR ROLE REQUIRED
Site: https://accident.innovatcs.com
================================================================

PROBLEM:
- GET https://accident.innovatcs.com/wp-json/wp/v2/posts?per_page=1  -> 200 OK (READ works)
- POST https://accident.innovatcs.com/wp-json/wp/v2/posts  -> 401 rest_cannot_create
- Means WP Application Password user role is Subscriber or Contributor (cannot publish_posts)

SOLUTION - 7 STEPS FOR MARUF (2 minutes):

1. Login to WordPress Admin:
   https://accident.innovatcs.com/wp-admin
   Use admin credentials you have.

2. Go to Users > All Users
   Find the user that has the Application Password (usually 'admin' or the user you used for RankForge)
   Click "Edit" under that user.

3. Change Role Dropdown:
   - BEFORE: Role = Subscriber (or Contributor)  <- cannot publish
   - AFTER:  Role = Editor  (or Administrator)  <- can publish_posts
   Example: Click Role dropdown -> select "Editor" -> Save consideration: Editor is safest for demo (can publish but not full admin)

4. Click "Update User" button at bottom (Save).

5. Regenerate Application Password (important - role change best with new password):
   - Still in Users > Profile (or Users > Your Profile)
   - Scroll to "Application Passwords" section at bottom
   - Find old Application Password named "RankForge" or similar -> Click "Revoke" (delete old)
   - Under "Add New Application Password":
     New Application Password Name:  RankForge Demo
     Click "Add New Application Password"
   - COPY the new password shown: format "xxxx xxxx xxxx xxxx" (4 groups, 12 chars with spaces)
     Example: "aBcd EfGh IjKl MnOp"
     Keep this copied - you will paste into RankForge.

6. Paste New Password into RankForge:
   - Go to RankForge: http://localhost:3000/connectors  (or your RankForge /connectors page)
   - Find "WordPress" card
   - Site URL: https://accident.innovatcs.com (already filled)
   - Username: admin (or your WP username)
   - Application Password: paste the NEW copied password "xxxx xxxx xxxx xxxx" (with spaces)
   - Click "Test Connection"
     Expected result after fix:
       -> Status 200
       -> roles: ["editor"]  or ["administrator"]
       -> can_publish: true
       -> Message: "Connected as admin ✅ roles=['editor'] can_publish=True"
       -> Green dot ✅
     Before fix you saw:
       -> roles: ["subscriber"] can_publish False + yellow banner "WordPress user needs Editor role..."

7. Test Publish via curl (optional, proves fix):
   curl -X POST -H "User-Agent: Mozilla/5.0 RankForge/1.0" -u "admin:NEW_PASSWORD_WITHOUT_SPACES_OR_WITH" https://accident.innovatcs.com/wp-json/wp/v2/posts -H "Content-Type: application/json" -d '{"title":"Test","content":"Test content from RankForge","status":"draft"}'
   Expected: HTTP 201 Created with {"id": 734, "link": "https://accident.innovatcs.com/?p=734", ...}
   Before fix you got: HTTP 401 {"code":"rest_cannot_create","message":"Sorry, you are not allowed to create posts as this user."}

   If still 401, try alternative endpoint (Hostinger fallback):
   curl -X POST -H "User-Agent: Mozilla/5.0 RankForge/1.0" -u "admin:NEW_PASSWORD" "https://accident.innovatcs.com/?rest_route=/wp/v2/posts" -H "Content-Type: application/json" -d '{"title":"Test","content":"Test","status":"draft"}'
   Should also return 201.

================================================================
WHAT RANKFORGE DOES AFTER FIX:
- RankForge will call check_publish_capability():
    GET https://accident.innovatcs.com/wp-json/wp/v2/users/me with your auth
    Check roles: if ["editor"] or ["administrator"] -> can_publish True -> allow POST
- publish_post_via_crew will then:
    POST https://accident.innovatcs.com/wp-json/wp/v2/posts with payload title/content/slug/status=draft + Yoast meta
    Expect 201 -> saves wordpress_post_id 734+, wordpress_url https://accident.innovatcs.com/?p=734 to blogs table
    Returns success True + edit_url https://accident.innovatcs.com/wp-admin/post.php?post=734&action=edit
- Dashboard banner will turn GREEN "WordPress connected - Editor role OK - can publish"

================================================================
DEMO FALLBACK IF ROLE STILL NOT FIXED (graceful):
- RankForge does NOT deactivate wordpress_connections.is_active (keeps true because READ 200 works)
- Saves to blog_approvals:
    status: pending
    pending_reason: "WP role needs Editor - see dashboard banner - current role: ['subscriber'] - cannot publish - Go to WP Admin > Users > Role = Editor"
- Dashboard shows YELLOW banner: "WordPress user needs Editor role - Go to WP Admin > Users > Role = Editor - current role: subscriber - cannot publish"
- Approval queue shows card with:
    HTML preview (real Crew generated 2500+ words, live generation)
    SEO badges 85+, citations [1][2], grounding 0.85
    Button: "Ready to publish - needs Editor role"
    Message: "Publish will work after role fix in 2 min - see fix_wp_role.py"
- During demo call, Maruf can fix role in 2 min, then click "Retry Publish" button which calls publish_post_via_crew again with fallback endpoints (/wp-json/ and /?rest_route/) -> 201 success.

================================================================
WORDPRESS CODE CHECK (for developer):
- backend/services/wordpress_service.py:check_publish_capability() -> GET users/me
- backend/services/wordpress_service.py:publish_post_via_crew() -> on 401 rest_cannot_create returns {error:"role", fix_instructions:"WP Admin > Users > Role = Editor"}
- Does NOT set is_active=False on 401 (only on 403 Hostinger)
- Dashboard banner: yellow "needs Editor role"

================================================================
VERIFY COMMANDS:
python backend/scripts/fix_wp_role.py --check
python backend/scripts/fix_wp_role.py --check --site https://accident.innovatcs.com --user admin --password "your app password here"

Expected after fix:
  {"connected": true, "status_code": 200, "roles": ["editor"], "can_publish": true, "message": "Connected as admin roles=['editor'] can_publish=True"}
  POST test -> 201

Before fix:
  {"connected": true, "status_code": 200, "roles": ["subscriber"], "can_publish": false, "warning": "WordPress user needs Editor role..."}
  POST -> 401 rest_cannot_create

================================================================
"""

async def check_site(site_url: str, username: str, password: str):
    from backend.services.wordpress_service import WordPressService
    svc = WordPressService(website_id="check")
    print(f"\n[Check] Site: {site_url}")
    print(f"[Check] User: {username}")
    print(f"[Check] Testing GET /wp-json/wp/v2/users/me ...")
    res = await svc.test_connection(site_url, username, password)
    print(f"  Test connection: {res}")
    if res.get("roles"):
        print(f"  Roles: {res.get('roles')}")
        print(f"  Can publish: {res.get('can_publish')}")
        if res.get("warning"):
            print(f"  WARNING (yellow banner): {res.get('warning')}")
            print(f"  -> FIX: WP Admin > Users > Role = Editor (see instructions)")
        elif res.get("can_publish"):
            print(f"  ✅ Role OK - can publish (Editor/Administrator)")
        else:
            print(f"  ⚠️ Unknown role - may not be able to publish")
    if not res.get("connected"):
        print(f"  Not connected: {res.get('message')}")
        if res.get("status_code") == 401 and "rest_cannot_create" in str(res.get("message")):
            print(f"  -> 401 rest_cannot_create = role needs Editor")
        return res
    # Check publish capability via dedicated method
    print(f"\n[Check] check_publish_capability() ...")
    cap = await svc.check_publish_capability(site_url, username, password)
    print(f"  Capability: {cap}")
    # Try real POST draft (dry run) - will create draft if role OK
    if cap.get("can_publish"):
        print(f"\n[Check] Testing real POST /wp-json/wp/v2/posts draft (will create Test draft then delete hint)...")
        import httpx
        headers = {"User-Agent": "Mozilla/5.0 RankForge/1.0", "Content-Type": "application/json"}
        payload = {"title": "RankForge Test Draft - Check Role", "content": "Test content - verifying Editor role can create posts - safe to delete.", "status": "draft"}
        # Use publish_with_fallback helper
        try:
            resp = await svc.publish_with_fallback(site_url, username, password, payload)
            if resp is not None:
                print(f"  POST status: {resp.status_code}")
                try:
                    j = resp.json()
                    print(f"  POST response: {str(j)[:500]}")
                except Exception:
                    print(f"  POST text: {resp.text[:500]}")
                if resp.status_code in (200, 201):
                    print(f"  ✅ POST 201 SUCCESS - role can publish! WordPress POST works - site ready for demo")
                    print(f"  Test draft created - you can delete it in WP Admin > Posts")
                elif resp.status_code == 401:
                    print(f"  ❌ POST 401 rest_cannot_create - role still Subscriber/Contributor - needs Editor")
                    print(f"  -> Go to WP Admin > Users > Role = Editor per instructions above")
                elif resp.status_code == 403:
                    print(f"  403 Hostinger bot protection - try ?rest_route fallback, contact Hostinger to whitelist /wp-json/")
                else:
                    print(f"  Unexpected POST status {resp.status_code}")
            else:
                print(f"  POST returned no response")
        except Exception as e:
            print(f"  POST check failed: {e}")
    else:
        print(f"\n  Skipping POST draft because can_publish=False - fix role first")
        print(f"  After you change role to Editor, re-run this check script - should then show can_publish=True and POST 201")
    return res

def print_instructions():
    print(INSTRUCTIONS)

async def main():
    parser = argparse.ArgumentParser(description="Fix WordPress 401 rest_cannot_create - Editor Role")
    parser.add_argument("--check", action="store_true", help="Check current WP role and POST capability")
    parser.add_argument("--instructions", action="store_true", help="Print 7-step fix instructions")
    parser.add_argument("--site", default=os.getenv("WORDPRESS_SITE_URL") or os.getenv("WORDPRESS_URL") or "https://accident.innovatcs.com", help="WP site URL")
    parser.add_argument("--user", default=os.getenv("WORDPRESS_USERNAME") or os.getenv("WORDPRESS_USER") or "admin", help="WP username")
    parser.add_argument("--password", default=os.getenv("WORDPRESS_APP_PASSWORD") or "", help="WP Application Password (xxxx xxxx xxxx xxxx)")
    args = parser.parse_args()

    if args.instructions or not args.check:
        print_instructions()
    if args.check:
        if not args.password:
            print("ERROR: --password required for --check (or set WORDPRESS_APP_PASSWORD env)")
            print("Example: python backend/scripts/fix_wp_role.py --check --password 'xxxx xxxx xxxx xxxx'")
            print("\nShowing instructions anyway:")
            print_instructions()
            sys.exit(1)
        await check_site(args.site, args.user, args.password)
        print("\n[Done] Check complete. If roles=['editor'] and POST 201 - ready for demo.")
        print("       If roles=['subscriber'] and POST 401 - follow 7 steps above to fix in WP Admin (2 min).")

if __name__ == "__main__":
    asyncio.run(main())
