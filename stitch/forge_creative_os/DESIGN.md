# Design System: The Obsidian Workbench

## 1. Overview & Creative North Star

### Creative North Star: "The Digital Lithograph"
This design system is built for the high-performance creative. It moves away from the "cluttered dashboard" trope and toward the "Digital Lithograph"—a workspace that feels etched, intentional, and deeply layered. We achieve this through **Tonal Depth** rather than structural lines, and **Intentional Asymmetry** to guide the eye toward the creative canvas.

The system breaks the "bootstrap template" look by utilizing high-contrast typography scales and overlapping glassmorphism elements. By treating the UI as a series of stacked, semi-transparent plates rather than a flat grid, we create a "production-ready" environment that feels as premium as the assets being created within it.

---

## 2. Colors & Surface Architecture

The palette is rooted in deep slates and charcoals to minimize eye strain during long production sessions, with vibrant electric accents to denote action and "live" states.

### The "No-Line" Rule
**Standard 1px solid borders for sectioning are strictly prohibited.** To define boundaries, designers must use background color shifts. For example, a `surface-container-low` side panel sitting against a `surface` background creates a clean, sophisticated break without the visual "noise" of a line.

### Surface Hierarchy & Nesting
Instead of a flat grid, use the Tiered Surface model to create a physical sense of depth.
- **Base Layer:** `surface` (#0b1326) – The foundation of the application.
- **Structural Nesting:** Use `surface-container-low` (#131b2e) for secondary panels and `surface-container-high` (#222a3d) for active workspace elements.
- **The "Glass & Gradient" Rule:** For floating modals, command palettes, or tooltips, use `surface-bright` (#31394d) at 60% opacity with a `backdrop-filter: blur(12px)`. This "frosted glass" effect allows the workbench colors to bleed through, softening the interface.

### Signature Textures
Main CTAs and Hero states should utilize a subtle linear gradient: `primary` (#c0c1ff) to `primary-container` (#8083ff) at 135 degrees. This provides a "liquid" feel that flat hex codes cannot replicate.

---

## 3. Typography: The Editorial Edge

We pair the precision of **Inter** with the architectural strength of **Manrope**.

*   **Display & Headlines (Manrope):** Use `display-lg` (3.5rem) and `headline-md` (1.75rem) to create an editorial, high-end feel for project titles and workspace headers. The wider tracking of Manrope feels authoritative and "custom."
*   **Body & Labels (Inter):** All functional data, asset metadata, and tooltips use Inter. `body-md` (0.875rem) is our workhorse for legibility.
*   **Visual Hierarchy:** Contrast is our primary tool. Pair a `headline-sm` project title in `on-surface` with a `label-sm` timestamp in `outline` to create immediate clarity through scale and weight, not just color.

---

## 4. Elevation & Depth

### The Layering Principle
Depth is achieved by "stacking" the surface tiers.
1. **Background:** `surface-dim`
2. **Section:** `surface-container-low`
3. **Card/Item:** `surface-container-lowest` (to create a "sunken" asset well) or `surface-container-highest` (to create a "raised" preview).

### Ambient Shadows
When an element must float (e.g., a detached color picker), use an extra-diffused shadow: `box-shadow: 0 20px 40px rgba(6, 14, 32, 0.4)`. The shadow color must be a tinted version of `surface-container-lowest`, never pure black, to maintain a natural, ambient light appearance.

### The "Ghost Border" Fallback
If a border is required for accessibility, use the "Ghost Border": `outline-variant` (#464554) at **15% opacity**. This provides a hint of a container without breaking the "No-Line" rule.

---

## 5. Components

### Sophisticated Asset Cards
*   **Structure:** No borders. Use `surface-container-low` for the card body. 
*   **Interaction:** On hover, the background shifts to `surface-container-high` and the `secondary` (#adc6ff) "Ghost Border" increases to 30% opacity. 
*   **No Dividers:** Separate metadata from the preview image using `spacing-4` (0.9rem) of vertical whitespace.

### Status Badges (The "Pulse" Component)
*   **Style:** Small, pill-shaped (`rounded-full`) using `secondary-container`.
*   **Micro-animation:** Async tasks (rendering, uploading) should feature a subtle 2s "breath" animation (opacity 100% to 60%) on the badge background to indicate life without distracting the user.

### Slim Sidebar Navigation
*   **Width:** Fixed at `spacing-20` (4.5rem).
*   **Style:** `surface-container-low` with a 1px "Ghost Border" only on the right edge.
*   **Icons:** Use `outline` color for inactive states; transition to `primary` (#c0c1ff) with a vertical glow bar (2px width) on the left for the active state.

### Buttons & Inputs
*   **Primary Button:** Gradient fill (`primary` to `primary-container`), `rounded-md` (0.375rem). Text is `on-primary` (#1000a9).
*   **Input Fields:** `surface-container-highest` background, no border. On focus, a 1px ghost border of `primary` appears with a subtle outer glow.

---

## 6. Do’s and Don’ts

### Do:
*   **Use Whitespace as a Tool:** Use `spacing-8` or `spacing-10` to separate major functional groups instead of lines.
*   **Embrace Tonal Shifts:** Use the difference between `surface-container-low` and `surface-container-high` to guide the user's focus.
*   **Apply Glassmorphism Sparingly:** Save the backdrop blur for high-context overlays like right-click menus or floating tool palettes.

### Don’t:
*   **Don't use 100% Opaque Borders:** This shatters the "Digital Lithograph" vibe and makes the tool feel like a legacy spreadsheet application.
*   **Don't use pure Black (#000000):** It is too heavy for this palette. Use `surface-container-lowest` (#060e20) for the deepest shadows.
*   **Don't crowd the Sidebar:** Keep the slim sidebar reserved for top-level navigation only. Use nested "Ghost" containers within the main stage for secondary sub-menus.