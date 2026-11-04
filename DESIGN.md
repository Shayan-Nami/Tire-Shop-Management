---
name: Tire Manager
description: A charcoal and amber document board for daily tire-shop operations.
colors:
  surface: "#ffffff"
  canvas: "#f6f7f8"
  line: "#dce2e7"
  ink: "#202a35"
  muted: "#596977"
  accent: "#d18b23"
  accent-hover: "#e5aa4b"
  accent-soft: "#fff8eb"
  rail-text: "#c3ccd4"
  rail-line: "#354451"
  rail-hover: "#293641"
  dark-canvas: "#131b24"
  dark-ink: "#eef1f3"
  dark-muted: "#b0bdc8"
  dark-accent-soft: "#302719"
typography:
  headline:
    fontFamily: "Vazirmatn, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "26px"
    fontWeight: 800
    lineHeight: 1.6
  title:
    fontSize: "15px"
    fontWeight: 750
  body:
    fontFamily: "Vazirmatn, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif"
    fontSize: "13px"
    lineHeight: 1.75
  label:
    fontSize: "12px"
    fontWeight: 600
rounded:
  status: "6px"
  control: "8px"
  panel: "12px"
spacing:
  compact: "8px"
  field: "12px"
  inset: "16px"
  section: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
  navigation-active:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "11px 12px"
---

# Design System: Tire Manager

## Overview

**Visual direction: a workspace for shop documents**

A workspace for daily tire-shop operations: cool gray surfaces, matte panels, a charcoal navigation rail and amber actions. Grouped navigation and aligned figures support quick scanning of invoices, stock and payments.

The system covers the thirteen existing routes, including login. Persian RTL is the primary operating language; the language switch also supports English/LTR interface copy, forms, print labels, status labels and locale-aware formatting. Shop-entered content and unknown server validation messages retain their source language. Light and dark preferences share the same geometry and semantic surface roles.

**Key Characteristics:**
- Dense, legible operational documents.
- Amber actions and active navigation on neutral surfaces.
- Tabular amounts, labeled states and responsive tables.

Implementation references: `frontend/src/index.css`, `frontend/tailwind.config.js`, `frontend/index.html`, shared layout, dashboard, catalog and receipt form components. The shared stylesheet overrides some older utility classes.

## Colors

Amber supplies operational emphasis against a cool neutral workspace.

### Primary

- **Action Amber** (`accent`): primary actions and active rail destinations; charcoal lettering remains legible on the fill.
- **Light Amber** (`accent-hover`): primary hover and rail brand accents.
- **Amber Paper** (`accent-soft`): document totals and attention counts.

### Neutral

- **Matte Surface**, **Cool Canvas**, **Document Line**: panel, workspace and divider roles.
- **Charcoal Ink**, **Slate Metadata**: primary text and secondary context.
- **Rail Text**, **Rail Line**, **Rail Hover**: charcoal navigation's readable labels, separators and hover fill.
- Dark mode maps surface to charcoal ink, canvas to dark canvas, line to rail line, ink to dark ink, muted to dark muted and accent-soft to dark accent-soft. Accent stays amber. These are role substitutions, not a separate layout.
- Existing semantic emerald, rose and amber utility treatments identify financial outcomes, errors and warnings; preserve accompanying labels rather than making hue the only state cue. They do not introduce additional brand accents.

**The Action Amber Rule.** Use amber for primary actions, selection and attention; keep ordinary document surfaces neutral.

## Typography

**Display Font:** Vazirmatn with the body fallback stack.
**Body Font:** Vazirmatn, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif.

**Character:** One Persian-capable family carries the hierarchy through size and weight. Display-scale lettering is confined to login; operational pages prioritize amounts and compact row labels.

### Hierarchy

- **Headline:** page headings use the frontmatter role, reduced to (22px) below the mobile breakpoint.
- **Title:** panel headings use (15px, weight 750); modal headings use (17px).
- **Body:** labels, fields and table rows commonly use (13px); table cells use (1.8) line-height and explanatory page text uses (1.9).
- **Label:** table headers and utility metadata use (12px); supporting row metadata commonly uses (11px).
- Login has a distinct brand headline (`clamp(32px, 3.7vw, 54px)`, weight 800, line-height 1.65) and a (28px) form heading. Do not export that display scale to operational pages.
- Mobile fields rise to (16px) while keeping the same family. Body font features enable ss01, ss02, cv01 and cv02.

**The Figure Alignment Rule.** Use tabular numerals for comparable amounts and quantities; keep units and document states explicit.

## Layout

The authenticated shell fills the dynamic viewport. A fixed-width (244px) charcoal rail sits on the RTL start side; the main workspace scrolls independently under a (76px) utility header. Content is centered with a maximum width of (1440px). Desktop workspace padding is (28px 32px 40px); page sections use a (24px) gap.

Below (1200px), workspace and header side padding become (24px), and dashboard split panels stack. Below (768px), the persistent rail becomes a native modal drawer with a maximum width of (88vw); workspace padding becomes (20px 16px) with a safe-area-aware bottom inset. Header utilities wrap, page section gaps become (20px), and summary cells become a two-by-two grid. At (380px) and below, header tools occupy a separate full-width row. A duplicate header primary action is only exposed at (1536px) and above.

Tables retain their columns with horizontal overflow containment; on mobile the shared table minimum width is (620px). Dashboard middle panels use a (1.8:1) split, and the lower board a (1.4:1) split before stacking. These are dashboard compositions, not required grids for every route. Filters wrap and the search field becomes full width on mobile. Invoice summaries stop sticking on mobile.

Login uses two equal columns on desktop, then a compact brand band and stacked form on mobile. Printing hides the shell and exposes the invoice document; thermal output has a dedicated (80mm) receipt treatment.

## Elevation & Depth

Ordinary panels are flat, separated by neutral fill and fine borders. Dashed seams belong to selected document boundaries, not every container. The native drawer and shared dialogs use a dark backdrop (`rgb(19 27 36 / .65)`). Shared modal cards carry a soft overlay shadow (`0 24px 64px -24px rgb(0 0 0 / .35)`). Legacy form overlays retain some local treatments; they are not a separate elevation vocabulary.

**The Document Seam Rule.** Separate ordinary panels with tone and fine borders; reserve dashed seams for document totals, attention rows and selected document boundaries.

## Shapes

Controls and navigation have gently curved corners through the control radius; panels and modal cards use the panel radius. Table state tags are compact rounded rectangles through the status radius. Document total bands are square-edged with dashed block borders. Fine solid borders define fields, panels and toolbar buttons. Lucide SVG line icons accompany controls and navigation.

## Components

### Buttons

Primary actions use amber fill, charcoal lettering, weight (800), a (44px) minimum height, and the frontmatter padding. Hover lightens the amber; disabled primary actions use opacity (.5). Secondary actions use a surface fill and line border, switching to canvas on hover. General icon controls are (40px) minimum, rising to (44px) on mobile. Table icons are (36px) on desktop and (44px) on mobile.

Keyboard focus is an amber (2px) outline offset by (3px). Shared state transitions last (150ms) with ease-out. Reduced-motion preference collapses transitions and animations to (.01ms).

### Chips

Table state tags use (11px) text, (4px 9px) padding and the status radius. Semantic colors and textual status identify workflow state; tags are not standalone decoration.

### Cards / Containers

Panels use the surface role, line border and panel radius with no resting shadow. Panel headings use (20px 22px) padding; mobile headings use (17px 16px). Filter bars use (16px), reduced to (12px) on mobile. Preserve document-specific inner layouts rather than assigning one universal card padding.

### Inputs / Fields

Fields use surface fill, line borders, control radius and (42px) desktop minimum height. Hover strengthens the border; focus switches to amber with a (2px) outline offset by (2px). Read-only and disabled fields use canvas fill and muted text. Mobile minimum height is (44px). Textareas start at (88px), pad vertically by (10px), and resize vertically. Login fields have a distinct (48px) minimum height and icon-aware padding.

### Navigation

Grouped role-filtered routes use (13px) labels, Lucide icons and (44px) minimum rows. The active destination has amber fill, charcoal lettering and an inline directional indicator; hover uses rail-hover fill. Logical inline spacing and indicator rotation follow document direction. The mobile drawer uses the shared native dialog wrapper, browser modal focus containment, Escape dismissal when not busy, and trigger focus restoration.

### Tables and summary strips

Table headers use canvas fill, muted text and (14px 18px) padding; cells use (15px 18px), changing together to (13px 14px) on mobile. Row hover uses canvas. Summary strips divide aligned figures with fine inline separators and mobile row seams; they are not four independently elevated cards.

### Dialogs and forms

The reusable native dialog wrapper is used for the mobile drawer and some shared overlays. Catalog, finance and other form dialogs also retain conventional overlay markup and local layouts, so native focus containment and Escape dismissal are not available in every form. Shared modal cards are scrollable, constrained to viewport height minus (48px), or (24px) on mobile, with a dashed header boundary. Keep submission, error and busy behavior intact when extending forms.

## Do's and Don'ts

### Do:
- **Do** reuse the shared surface, canvas, ink, muted, line and accent roles in both themes.
- **Do** preserve logical inline alignment and visible keyboard focus when extending RTL/LTR surfaces.
- **Do** keep tables horizontally scrollable on narrow screens and provide readable touch controls.
- **Do** preserve role-filtered navigation, existing form behavior and isolated invoice printing.

### Don't:
- **Don't** add decorative controls that distract from operational tasks.
- **Don't** apply modal shadows to ordinary resting panels.
- **Don't** treat untranslated server messages or residual legacy modal styling as a new component standard.

Known inconsistencies include legacy close controls, small helper text and differences in local modal/action styling. Use the shared controls when updating these screens.
