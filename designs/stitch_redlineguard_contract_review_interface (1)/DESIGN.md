---
name: RedlineGuard
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#414849'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#717879'
  outline-variant: '#c0c8c9'
  surface-tint: '#3c656a'
  primary: '#002428'
  on-primary: '#ffffff'
  primary-container: '#0d3b40'
  on-primary-container: '#7ba5ab'
  inverse-primary: '#a3ced4'
  secondary: '#7a5823'
  on-secondary: '#ffffff'
  secondary-container: '#fed08f'
  on-secondary-container: '#795722'
  tertiary: '#4a0002'
  on-tertiary: '#ffffff'
  tertiary-container: '#720006'
  on-tertiary-container: '#ff7265'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#bfeaf0'
  primary-fixed-dim: '#a3ced4'
  on-primary-fixed: '#001f23'
  on-primary-fixed-variant: '#234d52'
  secondary-fixed: '#ffddb1'
  secondary-fixed-dim: '#ecbf7f'
  on-secondary-fixed: '#291800'
  on-secondary-fixed-variant: '#5f410c'
  tertiary-fixed: '#ffdad6'
  tertiary-fixed-dim: '#ffb4ab'
  on-tertiary-fixed: '#410002'
  on-tertiary-fixed-variant: '#93000b'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Source Serif 4
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Source Serif 4
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-md:
    fontFamily: Source Serif 4
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  body-lg:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-md:
    fontFamily: Hanken Grotesk
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.03em
  mono-sm:
    fontFamily: jetbrainsMono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  container-max: 1440px
  sidebar-width: 280px
  gutter: 24px
  margin-page: 40px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style
The design system is engineered for high-stakes legal review, prioritizing cognitive clarity, precision, and executive authority. The brand personality is stoic, professional, and uncompromisingly utilitarian. It avoids the whimsical trends of consumer SaaS in favor of a "Modern Institutional" aesthetic that mirrors the gravitas of a high-end law firm.

The style is characterized by:
- **Minimalism:** Aggressive use of whitespace to reduce "visual noise" during complex document analysis.
- **Precision:** Sharp alignment and consistent grid logic to convey reliability.
- **High-Fidelity:** Subtle use of hairline borders and micro-interactions that feel deliberate rather than decorative.
- **Calmness:** A muted palette that allows critical alerts (redlines/risks) to surface without competing with the UI.

## Colors
The color strategy employs a "Signal vs. Noise" approach. The interface remains largely monochromatic, using neutral grays to define the environment, while chromatic colors are reserved for functional status and branding.

- **Primary (Deep Teal):** Used for navigation, primary actions, and brand presence. It conveys stability and depth.
- **Secondary (Muted Gold):** Used sparingly for highlighting specific contractual clauses or premium features.
- **Functional (Amber/Red):** High-contrast tones strictly reserved for risk detection, warnings, and deleted text in redlines.
- **Backgrounds:** A tiered system of off-whites (`#F8FAFC`, `#F1F5F9`) to separate document workspaces from utility panels.

## Typography
The typography system creates a sophisticated dialogue between tradition and technology. 

- **Headlines:** Source Serif 4 provides a literary, authoritative feel reminiscent of legal briefs and printed statutes. Use semi-bold weights for hierarchy.
- **UI & Body:** Hanken Grotesk is chosen for its contemporary, sharp geometric qualities, ensuring high legibility in dense data tables and long-form contract text.
- **Scale:** Maintain a strict hierarchy. Use uppercase labels for metadata and section headers to provide a structural "skeleton" to the page.
- **Mono:** JetBrains Mono is utilized for versioning numbers, timestamps, and metadata to emphasize technical precision.

## Layout & Spacing
This design system utilizes a structured, desktop-first 12-column grid. The philosophy is "focus-centric," meaning the central workspace (the document) is protected by generous margins, while utility panels are docked to the periphery.

- **Breakpoints:** Desktop (1440px+), Laptop (1280px), Tablet (1024px). Mobile is treated as a "read-only/review" state, not a primary editing environment.
- **Rhythm:** A 4px baseline grid ensures vertical rhythm. Elements are spaced in multiples of 8px (8, 16, 24, 32, 48, 64) to maintain consistency.
- **Layout Model:** Fixed sidebar for navigation, fluid central workspace for document editing, and a collapsible right-hand panel for "Risk Analysis" and "Comments."

## Elevation & Depth
Depth is communicated through **Tonal Layering** and **Low-Contrast Outlines** rather than dramatic shadows.

- **Surface Levels:** 
  - Level 0: `#F8FAFC` (Main background)
  - Level 1: `#FFFFFF` (Workspace/Document canvas)
  - Level 2: `#F1F5F9` (Sidebar and utility panels)
- **Outlines:** Use 1px borders in `#E2E8F0` for structural separation.
- **Shadows:** Only used for "floating" elements like dropdown menus or modals. These should be "Quiet Shadows": `0 4px 12px rgba(15, 23, 42, 0.08)`, extremely diffused with no heavy dark spots.
- **Focus:** Active states use a subtle 2px inset border of the primary Teal color or a soft background tint.

## Shapes
The shape language is "Soft" yet disciplined. Standard UI components use a 4px (0.25rem) radius to feel modern but structured. 

- **Inputs & Buttons:** 4px radius.
- **Cards & Modals:** 8px (0.5rem) radius for a slightly softer container feel.
- **Selection Indicators:** Sharp 0px corners for vertical "active" bars in sidebars to maintain a sense of architectural alignment.
- Avoid large rounds or pills; keep shapes "architectural."

## Components
- **Buttons:** Primary buttons are solid Deep Teal with white text. Secondary buttons use a 1px border. No gradients or shadows on hover; instead, use a 10% darken effect.
- **Input Fields:** Rectangular with a 1px Slate-200 border. Labels are always "Label-MD" (Hanken Grotesk, Uppercase) positioned above the field.
- **Risk Chips:** Rectangular with a subtle background tint (e.g., Soft Red background with Deep Red text) for identifying high-risk clauses.
- **Contract Cards:** Minimalist white cards with a 1px border. Use a vertical accent bar on the left to indicate status (Draft, Reviewed, Signed).
- **Redline Indicators:** Deleted text is shown with a light red background and strikethrough; additions are shown with a light teal background and underline.
- **Data Tables:** No vertical borders. Use horizontal dividers in Slate-100. Row height should be generous (48px+) to allow for comfortable scanning.