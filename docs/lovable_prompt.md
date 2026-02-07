# Lovable Frontend Prompt

Copy and paste this into Lovable to generate the frontend:

---

**Project**: "AdminHero" - A Voice-First French Bureaucracy Copilot.
**Stack**: React, Vite, TailwindCSS, Shadcn/UI, Lucide Icons, Framer Motion.

**Goal**: Create a stunning, high-end "Glassmorphism" interface for a voice assistant app.

**Core Features**:

1.  **Hero Section**:
    - A beautiful, clean background (subtle gradient or abstract shapes).
    - A **Large, Central Microphone Button**.
        - Default: Pulse animation (subtle).
        - Active (Recording): intense ripple/wave animation (think Siri or Google Assistant).
        - Processing: Spinning/Loading state.
    - Clear typography: "Tell me what admin task you need help with..."

2.  **Interaction Flow**:
    - User clicks Mic -> Records Audio.
    - (Mock logic): When stopped, show "Thinking...".
    - **Result View**: Two cards appear (staggered animation).
        1.  **The "Insight" Card**: A clear, simple explanation of the situation in the requester's language.
        2.  **The "Action" Card**: The formal French email/letter ready to send.
        - **Action Buttons**: "Send", "Ask Follow-up".

3.  **API Integration (Important)**:
    - The app needs to send the recorded audio `Blob` to an external API.
    - Create a service function `transcribeAndProcess(audioBlob)` that sends a POST request to `http://localhost:8000/api/v1/agent/process-audio`.
    - The backend will return JSON: `{ "explanation": "...", "email_draft": { "subject": "...", "body": "..." } }`.
    - Populate the cards with this response.

4.  **Aesthetics**:
    - Use a "Glass" effect for cards (white with low opacity, blur backdrop).
    - Rounded corners (xl or 2xl).
    - Typography: Inter or similar clean sans-serif.
    - Dark mode support (optional but preferred).

**Technical specific**:
- Use `framer-motion` for the mic animations.
- Use `lucide-react` for icons.

---
