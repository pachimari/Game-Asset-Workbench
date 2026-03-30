# Design System Strategy: Production-Grade Asset Workbench

## 1. Overview & Creative North Star: "The Kinetic Archive"
The Creative North Star for this design system is **"The Kinetic Archive."** 

Unlike generic consumer tools, this system is built for the high-velocity, high-density environment of game production. It rejects the "web-template" aesthetic in favor of a specialized "Production Grade" interface. It treats every AI-generated asset not as a static image, but as a unit of data moving through a pipeline. 

The visual language breaks the rigid, centered grid by utilizing **Functional Asymmetry**. Large-scale batch management areas are grounded on stable, low-tier surfaces, while candidate pools and configuration panels float with "glass" properties, suggesting their temporary, iterative nature. High-contrast typography scales ensure that even at extreme information densities, the hierarchy remains unmistakable for artists and planners.

---

## 2. Colors: Tonal Depth & The "No-Line" Mandate
The palette is rooted in `background: #060e20`. This is not a flat black, but a deep, oceanic navy that provides a more sophisticated "ink" feel than pure neutral grays.

### The "No-Line" Rule
To achieve a premium, seamless feel, **1px solid borders for sectioning are strictly prohibited.** Separation must be achieved through:
*   **Background Shifts:** Use `surface_container_low` for the main workspace and `surface_container_high` for sidebar utilities.
*   **Tonal Transitions:** Define boundaries by placing a `surface_container` element directly against the `surface_dim` background.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack of technical sheets. 
*   **Base:** `surface` (#060e20) for the global backdrop.
*   **Level 1 (Sections):** `surface_container_low` (#091328) for large batch management areas.
*   **Level 2 (Active Cards):** `surface_container` (#0f1930) for individual asset items.
*   **Level 3 (Pop-overs/Modals):** `surface_bright` (#1f2b49) to draw the eye to critical configurations.

### The "Glass & Signature" Rule
*   **Glassmorphism:** Use `primary` (#a3a6ff) at 8% opacity with a `backdrop-blur: 12px` for floating candidate pools. This prevents the dark theme from feeling heavy or claustrophobic.
*   **Signature Textures:** Main CTAs should use a subtle linear gradient from `primary` (#a3a6ff) to `primary_dim` (#6063ee) at a 135° angle to give buttons a "lathed metal" professional sheen.

---

## 3. Typography: High-Density Clarity
The system uses a Chinese-optimized stack: `PingFang SC`, `Microsoft YaHei`, and `Inter` for alphanumeric data.

*   **Display & Headline:** Used sparingly for dashboard stats. `headline-sm` (1.5rem) identifies the current Project/Sprint.
*   **Title (The Workhorse):** `title-sm` (1rem) is the standard for asset names. It uses `on_surface` (#dee5ff) for maximum legibility against dark backgrounds.
*   **Body & Labels (The Data):** `body-sm` (0.75rem) and `label-sm` (0.6875rem) are used for technical metadata (seed numbers, prompt tokens, dimensions). 
*   **Intentional Contrast:** Use `on_surface_variant` (#a3aac4) for secondary metadata to create "visual quiet" around the primary asset titles.

---

## 4. Elevation & Depth: Tonal Layering
Traditional drop shadows are too "dirty" for a high-density production tool. We use **Tonal Layering**.

*   **The Layering Principle:** To lift a "Provider Configuration" panel, do not add a shadow. Instead, place the `surface_container_highest` (#192540) panel over the `surface_container_low` (#091328) workspace. The contrast in lightness provides a cleaner, sharper "lift."
*   **Ambient Shadows:** If a floating element (like a context menu) requires a shadow, use a large blur (24px) at 6% opacity, using the `primary` color as the shadow tint rather than black.
*   **The Ghost Border:** If high-density data requires a container, use `outline_variant` (#40485d) at **15% opacity**. This creates a "suggestion" of a boundary without cluttering the artist's field of vision.

---

## 5. Components: Precision Tooling

### Buttons
*   **Primary:** Indigo gradient (`primary` to `primary_dim`). `rounded-sm` (0.125rem) to maintain a technical, "machined" look.
*   **Secondary:** Ghost style. No background, `outline` (#6d758c) at 20% opacity. 

### Cards & Asset Items
*   **Forbidden:** Divider lines between metadata rows.
*   **Rule:** Use `Spacing 2` (0.4rem) of vertical whitespace to separate "Prompt" from "Negative Prompt" within a card.
*   **Selection:** Indicated by a 2px `primary` left-border accent—never a full box outline.

### Precise Badges
*   Used for status (e.g., "Rendering," "Upscaling," "Approved").
*   **Style:** Minimalist. Solid `secondary_container` (#49339d) background with `label-sm` uppercase text. 

### Input Fields
*   **Focus State:** The background shifts to `surface_container_highest` (#192540) and the `primary` glow is applied only to the bottom 2px of the field.

### Specialized Component: The "Candidate Strip"
A horizontal scrolling container for AI iterations. Uses `surface_container_lowest` (#000000) to act as a "negative space" tray, making the colorful game icons pop.

---

## 6. Do's and Don'ts

### Do:
*   **Do** use `Spacing 1.5` (0.3rem) for tight technical data grids to maximize information density.
*   **Do** use `primary_fixed` (#9396ff) for active toggle states to ensure artists can see settings at a glance.
*   **Do** allow "overlapping" of the candidate pool over the main workbench to create a sense of workspace depth.

### Don't:
*   **Don't** use `rounded-xl` or `rounded-full` for functional containers; it feels too "consumer-soft." Stick to `sm` (0.125rem) and `md` (0.375rem).
*   **Don't** use pure white text (#FFFFFF). Always use `on_surface` (#dee5ff) to reduce eye strain during long production sessions.
*   **Don't** use "Concept" illustrations. Every pixel must serve a functional purpose—either as data, a control, or a structural layer.