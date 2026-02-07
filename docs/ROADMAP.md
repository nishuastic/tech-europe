# Roadmap

## ✅ Phase 1: Extreme MVP (Hackathon)

- [x] FastAPI backend with `/process-audio` endpoint
- [x] Gradium SDK integration (STT + TTS)
- [x] Dify API integration for RAG + LLM
- [x] Frontend setup (bureaucracy-buddy)
- [x] TTS "Listen" button for voice responses
- [ ] Dify Knowledge Base populated with French admin URLs

---

## 🔄 Phase 2: Polish

- [ ] **Conversation Memory**: Multi-turn with `conversation_id`
- [ ] **Alpic Skybridge**: ChatGPT App integration
- [ ] **More Data Sources**: service-public.fr, caf.fr, impots.gouv.fr
- [ ] **Auto-play TTS** on response (optional setting)

---

## 🌟 Phase 3: Vision (Real-time Phone Agent)

### Goal
Live call translation: You speak English ↔ AI translates in real-time ↔ French Hotline

### Architecture Options

1. **Twilio + OpenAI Realtime API**
2. **LiveKit Agents SDK** (WebRTC, lower latency)

### Voice Cloning for Personalization
- **Gradium Instant Voice Clone**: 10 seconds of audio → custom voice
- **Gradium Pro Voice Clone**: 30+ minutes → hyper-realistic voice
- Use cloned voice for TTS to maintain user's voice identity during translation
- API: `gradium.voices.create(client, audio_file="sample.wav", name="My Voice")`

### Real-time Voice Streaming
- **STT Streaming**: `client.stt_stream()` with chunked audio input
- **TTS Streaming**: `client.tts_stream()` for low-latency output
- Target latency: < 500ms end-to-end
- VAD (Voice Activity Detection): Use `inactivity_prob` to detect turn completion

### Implementation Flow
```
User Phone → Twilio Media Stream
     ↓
Gradium STT (streaming) → English text
     ↓
OpenAI/Dify → Translate to French
     ↓
Gradium TTS (streaming, cloned voice) → French audio
     ↓
CAF Hotline
```

---

## Ideas Backlog

- [ ] OCR: Scan French letters → Explain + Respond
- [ ] Calendar: Auto-schedule appointments
- [ ] PDF generation with signature
- [ ] Voice cloning onboarding flow (record 10s sample)
