# Lovable Landing Page Prompt

Copy and paste this into Lovable to generate the landing page:

---

**Project**: "AdminHero" Landing Page - A Voice-First French Bureaucracy Copilot.
**Vibe**: Apple-level polish. Premium SaaS. Not a hackathon project.

## Design System

**Typography**:
- Use **Inter** or **SF Pro Display** (fallback: system-ui) for headings
- Use **Inter** for body text
- Large, bold headings (clamp(2.5rem, 5vw, 4rem))
- Generous letter-spacing on headlines (-0.02em)

**Colors** (Dark Mode First):
- Background: `#09090B` (near-black)
- Surface: `#18181B` (zinc-900)
- Primary Accent: `#6366F1` (indigo-500) or `#8B5CF6` (violet-500)
- Text Primary: `#FAFAFA`
- Text Muted: `#A1A1AA`

**Spacing**: Use 8px grid. Generous whitespace. Let elements breathe.

---

## Sections

### 1. Hero
- **Layout**: Full viewport height, centered content
- **Headline**: "Navigate French Bureaucracy. In Any Language." (or similar)
- **Subhead**: One sentence explaining the value (muted color)
- **CTA**: Single, prominent button → "Try It Free" (gradient or solid primary)
- **Visual**: Subtle animated gradient orb or mesh in background (CSS only, no heavy assets)
- **Optional**: Small "Powered by AI" badge or trust indicators

### 2. Problem / Pain Points (Optional)
- 3-column grid with icons
- Short pain points: "Complex forms", "Language barriers", "Endless wait times"
- Minimalist icons (Lucide)

### 3. How It Works
- 3 steps, horizontal or vertical timeline
- Step 1: "Speak" (mic icon)
- Step 2: "Understand" (brain/lightbulb icon)
- Step 3: "Act" (send/email icon)
- Each step: icon + short title + one-line description

### 4. Features (Bento Grid)
- Use a **Bento Box** layout (asymmetric grid of cards)
- Cards with subtle glass effect or soft borders
- Features: "Multilingual", "Instant Drafts", "Legal Context", "Voice-First"
- Each card: icon + title + short description

### 5. CTA / Footer
- Simple centered CTA: "Ready to simplify your admin?" + Button
- Footer: minimal links, copyright, maybe social icons

---

## Interactions & Polish
- **Hover states**: Subtle scale (1.02) or glow on buttons/cards
- **Scroll animations**: Fade-in-up on sections (use Framer Motion or CSS)
- **Cursor**: Consider custom cursor or pointer effects on interactive elements
- **Micro-copy**: Friendly, confident tone. No jargon.

## Technical Notes
- Framework: React (Vite), TailwindCSS, Framer Motion
- Icons: Lucide React
- No placeholder images—use gradients, abstract shapes, or nothing
- Mobile-first responsive design
- Lighthouse score > 90

---

**Reference Aesthetic**: Linear.app, Vercel.com, Raycast.com, Resend.com
