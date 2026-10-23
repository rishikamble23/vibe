# SHELFLINE — Light Theme & Design Token Guide

This document defines the clean, modern **light-mode design system** for SHELFLINE, ensuring high legibility, professional calm, and operational clarity without visual fatigue.

---

## 1. Color Palette (Light Theme)

### Backgrounds & Surfaces
- **App Background (`--bg-app`)**: `#F4F6F9` (Soft clean cool gray-blue)
- **Surface / Card (`--bg-card`)**: `#FFFFFF` (Pure white)
- **Sidebar / Navigation (`--bg-nav`)**: `#FFFFFF` with `#E5E9F0` border
- **Hover State (`--bg-hover`)**: `#F0F3F7`
- **Active / Selected (`--bg-active)`**: `#EBF3FF`

### Text & Typography
- **Primary Text (`--text-primary`)**: `#1E293B` (Slate 800)
- **Secondary Text (`--text-secondary`)**: `#64748B` (Slate 500)
- **Muted Text (`--text-muted`)**: `#94A3B8` (Slate 400)
- **Heading Color (`--text-heading`)**: `#0F172A` (Slate 900)

### Semantic Status Colors (Accessible Light Mode)
- **Safe / Success (`--color-safe`)**:
  - Background: `#DCFCE7` (Green 100)
  - Text / Icon: `#166534` (Green 800)
  - Accent Bar: `#22C55E` (Green 500)
- **At Risk / Warning (`--color-warning`)**:
  - Background: `#FEF3C7` (Amber 100)
  - Text / Icon: `#92400E` (Amber 800)
  - Accent Bar: `#F59E0B` (Amber 500)
- **Critical / Danger (`--color-danger`)**:
  - Background: `#FEE2E2` (Red 100)
  - Text / Icon: `#991B1B` (Red 800)
  - Accent Bar: `#EF4444` (Red 500)
- **Info / Neutral (`--color-info`)**:
  - Background: `#E0F2FE` (Sky 100)
  - Text / Icon: `#0369A1` (Sky 800)
  - Accent Bar: `#0EA5E9` (Sky 500)

---

## 2. Typography & Hierarchy
- **Font Family**: Inter, system-ui, -apple-system, sans-serif
- **Page Title**: 24px / Bold (`#0F172A`)
- **Section Heading**: 18px / SemiBold (`#1E293B`)
- **Body Text**: 14px / Regular (`#1E293B`)
- **Metadata / Caption**: 12px / Medium (`#64748B`)
- **Mono / Timers**: JetBrains Mono or monospace (for countdowns and timestamps)

---

## 3. UI Components & Borders
- **Border Radius**: 
  - Cards & Containers: `12px`
  - Buttons & Inputs: `8px`
  - Badges & Chips: `6px`
- **Borders**: `1px solid #E2E8F0` (Slate 200)
- **Shadows**:
  - Cards: `0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)`
  - Floating Drawers: `0 10px 25px -5px rgba(0, 0, 0, 0.1)`
