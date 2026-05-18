# Spec: Profile Page Design

## Overview
Replaces the `/profile` stub with a fully designed, authenticated profile page.
All data is hardcoded this step — no DB queries until Step 5. The page
establishes the visual pattern for in-app (post-login) pages and uses a
card-based, fintech-style layout consistent with the Spendly design language:
soft shadows, rounded corners, CSS custom properties throughout, and Lucide icons.

## Depends on
- Step 01 — Database Setup (`users` table must exist)
- Step 02 — Registration (a user account must be creatable)
- Step 03 — Login and Logout (`session["user_id"]` and `session["user_name"]`
  set on login; `/profile` needs an authenticated session)

## Routes
- `GET /profile` — render the profile page — logged-in only

If `session.get("user_id")` is falsy, redirect to `url_for("login")`.

## Database changes
No database changes. All data is hardcoded context passed from the route.

## Templates
- **Create:** `templates/profile.html` — four-section page extending `base.html`:
  1. **Profile card** — boxed card surface; avatar circle with accent ring,
     name, email, "Member since" row with calendar icon
  2. **Stats row** — three `.stat-card` tiles with label + Lucide icon (top
     row) and value below (total spent, transaction count, top category)
  3. **Transactions table** — date, description, category badge, amount;
     row hover; amount right-aligned with tabular-nums
  4. **Category breakdown** — progress bars with name, bar, `%` label, amount;
     all bar colours via CSS variables
- **Modify:** `templates/base.html` —
  - Add `<a href="{{ url_for('profile') }}">Profile</a>` in the logged-in nav branch
  - Add Lucide CDN script tag before `</body>`

## Files to change
- `app.py` — implement `profile()`: auth guard, hardcoded context dicts, render template
- `templates/base.html` — Profile nav link + Lucide CDN

## Files to create
- `templates/profile.html` — profile page template
- `static/css/profile.css` — page-scoped styles; all colours via `--var`

## New dependencies
No new pip packages. Lucide loaded via CDN (unpkg), no npm.

## Layout
```
[Profile card — full width]
[Stats row — 3 equal columns]
[profile-bottom — 3fr | 2fr grid on desktop, stacked on mobile]
  ├── Recent Transactions (table)
  └── Spending by Category (progress bars)
```

## Rules for implementation
- No SQLAlchemy or ORMs — `get_db()` only if needed (not this step)
- Parameterised queries only — never f-strings in SQL
- Passwords hashed with werkzeug — never render `password_hash`
- Use CSS variables — never hardcode hex values in templates or CSS rules;
  new colour tokens go in `:root` inside `profile.css`
- `--shadow-card: 0 1px 2px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.06)`
  defined as a variable and reused across all cards
- All templates extend `base.html`
- `url_for()` for every internal link — never hardcode paths
- Login gate: `if not session.get("user_id"): return redirect(url_for("login"))`
- Category badge class: `tx-badge tx-badge--{{ tx.category | lower }}`
- Progress bar width via `style="width: {{ cat.pct }}%"` (safe — not a colour)
- Icons via `<i data-lucide="name"></i>`; `lucide.createIcons()` called in `main.js`
- CSS class prefixes: `.profile-*`, `.stat-*`, `.tx-*`, `.cat-*` — no global leakage
- Responsive: stats → 2-col on ≤640px; bottom grid → stacked on ≤768px

## Definition of done
- [ ] `GET /profile` unauthenticated redirects to `/login`
- [ ] `GET /profile` authenticated returns HTTP 200 and renders `profile.html`
- [ ] Profile card shows avatar initials, name, email, member-since with calendar icon
- [ ] Avatar has an accent-colour ring (`box-shadow: 0 0 0 4px var(--accent-light)`)
- [ ] Stats row shows 3 cards each with a Lucide icon + value
- [ ] Transaction table shows ≥ 3 rows; amounts are right-aligned
- [ ] Category breakdown shows ≥ 3 rows with progress bar, `%` label, and amount
- [ ] Profile nav link appears in the navbar when logged in
- [ ] No hex colour values appear directly in `profile.html`
- [ ] Logged-in users visiting `/` are redirected to `/profile`
- [ ] After login, user is redirected to `/profile` (not landing)
- [ ] App still starts on port 5001; other pages unaffected
