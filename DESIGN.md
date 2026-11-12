# Frontend Design Guide

## Overview

The frontend interface uses a charcoal (`#202a35`) and amber (`#d18b23`) document-board palette designed for daily tire-shop operations: cool gray workspace surfaces, flat matte panels, a charcoal navigation rail, and high-contrast amber primary actions.

The layout covers all fourteen routes, including login. Persian (RTL) is the default operating language, with English (LTR) support for interface copy, forms, print layouts, status badges, and locale-aware date/currency formatting. Light and dark themes share the same layout geometry and map semantic CSS variables across both modes.

Implementation files:
- `frontend/src/index.css`
- `frontend/tailwind.config.js`
- `frontend/index.html`
- `frontend/src/components/layout/`
- `frontend/src/components/ui/Modal.tsx`

## Color Tokens

Semantic CSS custom properties are defined in `frontend/src/index.css`:

| Token | Light Mode | Dark Mode | Role |
| --- | --- | --- | --- |
| `--surface` | `#ffffff` | `#202a35` | Card, modal, table, and input backgrounds |
| `--canvas` | `#f6f7f8` | `#131b24` | Main scrolling workspace and table header fill |
| `--line` | `#dce2e7` | `#354451` | Panel, table, and input borders |
| `--ink` | `#202a35` | `#eef1f3` | Primary body and heading text |
| `--muted` | `#596977` | `#b0bdc8` | Secondary labels, captions, and metadata |
| `--accent` | `#d18b23` | `#d18b23` | Primary buttons, active navigation, and focus outlines |
| `--accent-hover` | `#e5aa4b` | `#e5aa4b` | Primary action hover state |
| `--accent-soft` | `#fff8eb` | `#302719` | Highlighted document totals and attention badges |
| `--rail-text` | `#c3ccd4` | `#c3ccd4` | Navigation rail text |
| `--rail-line` | `#354451` | `#354451` | Navigation rail dividers |
| `--rail-hover` | `#293641` | `#293641` | Navigation item hover fill |

Semantic emerald, rose, and amber utility classes indicate payment states, validation errors, and stock warnings alongside explicit text labels.

## Typography

- **Font stack:** `Vazirmatn, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif`
- **Numeric alignment:** Financial figures, quantities, and invoice numbers use `font-variant-numeric: tabular-nums` (`.tabular-nums`) so vertical columns stay aligned across rows.
- **Scale:**
  - Page title (`.page-title`): `26px` (`22px` on mobile), weight `800`, line-height `1.6`
  - Panel title (`.panel-title`): `15px`, weight `750`
  - Modal heading: `17px`, weight `800`
  - Body and table cells: `13px`, line-height `1.75`–`1.8`
  - Table headers and field labels: `12px`, weight `600`–`700`
  - Mobile inputs: `16px` below `768px` to prevent automatic viewport zoom on mobile browsers

## Layout & Responsive Breakpoints

- **Desktop shell:** Full dynamic viewport height (`100dvh`) with a fixed `244px` charcoal sidebar on the inline-start side and an independently scrolling workspace under a `76px` header (`max-width: 1440px`, padding `28px 32px 40px`).
- **Below `1200px`:** Header and workspace horizontal padding narrow to `24px`, and split dashboard panels stack vertically.
- **Below `768px`:** The persistent sidebar collapses into a native `<dialog>` drawer (`Modal.tsx`, `max-width: 88vw`). Workspace padding adjusts to `20px 16px` with safe-area bottom inset, KPI summary strips wrap into a `2x2` grid, and filter bars stack cleanly.
- **Data tables:** `.table-scroll` wraps `.data-table` with horizontal overflow containment (`min-width: 620px` on mobile) so multi-column financial and catalog tables remain readable without breaking the page width.
- **Print media:** `@media print` hides `header`, `aside`, `.no-print`, `.no-print *`, and `.app-shell` siblings when `body:has(.invoice-modal-overlay)` is active, resets `html, body, #root, .app-shell, .workspace, main` and `.app-shell, .app-shell > div` (`height: auto`, `overflow: visible`, `display: block`) for multi-page printing, enforces `#000000` ink on `#ffffff` backgrounds across `.invoice-modal-card *`, and isolates `.invoice-modal-overlay` / `.invoice-modal-card` for A4 output (`@page { margin: 8mm; }`) or compact `80mm` thermal receipt printing (`@page thermal { size: 80mm auto; margin: 0; }` applied via `page: thermal` on `body:has(.thermal-receipt-mode)`, `.invoice-modal-overlay:has(.thermal-receipt-mode)`, `.invoice-modal-card:has(.thermal-receipt-mode)`, and `.thermal-receipt-mode` at `width: 80mm`, `max-width: 80mm`, `padding: 2mm`, `font-size: 11px`).

## Core UI Primitives

- **Buttons:** `.action-primary` uses `--accent` fill with `#202a35` text, weight `800`, `8px` radius, and `44px` minimum height. `.action-secondary` uses `--surface` fill with `--line` borders and `44px` minimum height. Standard UI icon/control buttons (`.ui-button`) maintain `40px` desktop (`36px` in `.data-table`) and `44px` mobile hit targets.
- **Panels:** `.surface-panel` uses flat `--surface` backgrounds, `1px solid var(--line)`, and `12px` border radius without drop shadows. Dashed document borders (`1px dashed var(--line)`) separate invoice totals and modal headers.
- **Inputs:** `.ui-field` uses `--surface` fill, `--line` borders, `8px` radius, and `42px` minimum height (`44px` and `16px` font-size on mobile), with a `2px solid var(--accent)` focus outline (`2px` offset).
- **Login form inputs:** `.login-form-card .ui-field` applies directional logical padding (`min-height: 48px; padding-block: 10px; padding-inline-start: 42px; padding-inline-end: 14px`), paired with `.login-form-card .field-icon` (`inset-inline-start: 14px; top: 16px`), `.login-form-card .password-input` (`padding-inline-end: 48px`), and `.login-form-card .password-toggle` (`inset-inline-end: 5px; top: 4px`) so icon and toggle clearances mirror automatically between RTL (Persian) and LTR (English).
- **Dialogs:** `src/components/ui/Modal.tsx` wraps the native HTML `<dialog>` element (`showModal()`, backdrop click handling, Escape dismissal, and focus restoration) for the mobile navigation drawer and quick-create dialogs, while `.modal-card` styles shared form overlays.
