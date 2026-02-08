import { useState, useEffect, useRef, useCallback } from "react";

/**
 * Call phases matching backend CallPhase enum
 */
export type CallPhase =
    | "gathering_info"
    | "ready_to_call"
    | "dialing"
    | "connected"
    | "caf_speaking"
    | "waiting_user"
    | "user_speaking"
    | "ended"
    | "failed";

/**
 * Transcript entry from the call
 */
export interface TranscriptEntry {
    speaker: "caf" | "user";
    french: string;
    english: string;
    timestamp: number;
    isFinal?: boolean;
}

/**
 * Call session state
 */
export interface CallSessionState {
    callId: string | null;
    phase: CallPhase;
    target: string;
    question: string;
    transcript: TranscriptEntry[];
    waitingForUser: boolean;
    error: string | null;
    // Agent-mediated response
    agentThinking: boolean;
    agentSuggestion: string | null;
}

const BACKEND_URL = "http://localhost:8000";
const API_BASE = `${BACKEND_URL}/api/v1/call`;
const WS_BASE = BACKEND_URL.replace(/^http/, "ws") + "/api/v1/call/ws";

/**
 * Hook for managing an interactive call session
 */
export function useCallSession() {
    const [state, setState] = useState<CallSessionState>({
        callId: null,
        phase: "gathering_info",
        target: "caf",
        question: "",
        transcript: [],
        waitingForUser: false,
        error: null,
        agentThinking: false,
        agentSuggestion: null,
    });

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttempts = useRef(0);

    /**
     * Connect to the call WebSocket
     */
    const connectWebSocket = useCallback((callId: string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            return;
        }

        const ws = new WebSocket(`${WS_BASE}/${callId}`);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("[Call] WebSocket connected");
            reconnectAttempts.current = 0;
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("[Call] WS Message:", data.type, data);

            switch (data.type) {
                case "session_state":
                    setState((prev) => ({
                        ...prev,
                        phase: data.phase,
                        target: data.target,
                        question: data.question,
                    }));
                    break;

                case "call_connected":
                    setState((prev) => ({ ...prev, phase: "connected" }));
                    break;

                case "caf_speaking_started":
                    setState((prev) => ({ ...prev, phase: "caf_speaking" }));
                    break;

                case "caf_said":
                    // Real-time transcript update (streaming)
                    setState((prev) => {
                        const transcript = [...prev.transcript];
                        // Update or add entry
                        const lastEntry = transcript[transcript.length - 1];
                        if (lastEntry?.speaker === "caf" && !lastEntry.isFinal) {
                            // Update existing streaming entry
                            transcript[transcript.length - 1] = {
                                ...lastEntry,
                                french: data.french,
                                english: data.english,
                            };
                        } else {
                            // Add new entry
                            transcript.push({
                                speaker: "caf",
                                french: data.french,
                                english: data.english,
                                timestamp: Date.now(),
                                isFinal: data.is_final,
                            });
                        }
                        return { ...prev, transcript };
                    });
                    break;

                case "caf_finished":
                    // Final transcript from CAF
                    setState((prev) => {
                        const transcript = [...prev.transcript];
                        const lastEntry = transcript[transcript.length - 1];
                        if (lastEntry?.speaker === "caf") {
                            transcript[transcript.length - 1] = {
                                ...lastEntry,
                                french: data.french,
                                english: data.english,
                                isFinal: true,
                            };
                        }
                        return { ...prev, transcript };
                    });
                    break;

                case "waiting_for_user":
                    setState((prev) => ({
                        ...prev,
                        phase: "waiting_user",
                        waitingForUser: true,
                        agentThinking: false,
                        agentSuggestion: null,
                    }));
                    break;

                case "agent_thinking":
                    // Agent is crafting a response
                    setState((prev) => ({
                        ...prev,
                        agentThinking: true,
                        agentSuggestion: null,
                    }));
                    break;

                case "agent_suggests":
                    // Agent has a suggested response
                    setState((prev) => {
                        // Add agent's suggestion to transcript
                        const transcript = [...prev.transcript];
                        transcript.push({
                            speaker: "user",
                            french: "",  // Will be translated
                            english: data.english,
                            timestamp: Date.now(),
                            isFinal: true,
                        });
                        return {
                            ...prev,
                            transcript,
                            agentThinking: false,
                            agentSuggestion: data.english,
                            waitingForUser: false,
                            phase: "user_speaking",
                        };
                    });
                    break;

                case "speaking_to_caf":
                    setState((prev) => ({
                        ...prev,
                        phase: "user_speaking",
                        waitingForUser: false,
                    }));
                    break;

                case "finished_speaking":
                    setState((prev) => ({ ...prev, phase: "caf_speaking" }));
                    break;

                case "call_ended":
                    setState((prev) => ({ ...prev, phase: "ended" }));
                    break;

                case "error":
                    setState((prev) => ({
                        ...prev,
                        phase: "failed",
                        error: data.message,
                    }));
                    break;
            }
        };

        ws.onerror = (error) => {
            console.error("[Call] WebSocket error:", error);
        };

        ws.onclose = () => {
            console.log("[Call] WebSocket closed");
            wsRef.current = null;
        };
    }, []);

    /**
     * Start a new call session
     */
    const startCall = useCallback(
        async (target: string, question: string) => {
            try {
                // 1. Create session
                const response = await fetch(`${API_BASE}/start`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ target, user_question: question }),
                });

                if (!response.ok) {
                    throw new Error("Failed to start call");
                }

                const data = await response.json();
                const callId = data.call_id;

                setState((prev) => ({
                    ...prev,
                    callId,
                    phase: data.phase,
                    target,
                    question,
                    transcript: [],
                    error: null,
                }));

                // 2. Connect WebSocket
                connectWebSocket(callId);

                // 3. Wait a moment for WebSocket, then dial
                await new Promise((resolve) => setTimeout(resolve, 500));

                const dialResponse = await fetch(`${API_BASE}/dial/${callId}`, {
                    method: "POST",
                });

                if (!dialResponse.ok) {
                    throw new Error("Failed to dial");
                }

                setState((prev) => ({ ...prev, phase: "dialing" }));
            } catch (error) {
                console.error("[Call] Start failed:", error);
                setState((prev) => ({
                    ...prev,
                    phase: "failed",
                    error: error instanceof Error ? error.message : "Unknown error",
                }));
            }
        },
        [connectWebSocket]
    );

    /**
     * Join an existing call session (for agent-initiated calls)
     * The agent already created the session and dialed, we just connect
     */
    const joinCall = useCallback(
        (callId: string, target: string = "caf") => {
            console.log("[Call] Joining existing call:", callId);

            setState((prev) => ({
                ...prev,
                callId,
                phase: "dialing",
                target,
                question: "Agent-initiated call",
                transcript: [],
                error: null,
            }));

            // Connect to the WebSocket for this call
            connectWebSocket(callId);
        },
        [connectWebSocket]
    );

    /**
     * Send a response to CAF
     */
    const sendResponse = useCallback((text: string) => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
            console.error("[Call] WebSocket not connected");
            return;
        }

        // Add to transcript immediately
        setState((prev) => ({
            ...prev,
            transcript: [
                ...prev.transcript,
                {
                    speaker: "user",
                    french: "", // Will be filled by backend
                    english: text,
                    timestamp: Date.now(),
                    isFinal: true,
                },
            ],
            waitingForUser: false,
        }));

        wsRef.current.send(
            JSON.stringify({
                type: "user_response",
                text,
            })
        );
    }, []);

    /**
     * End the call
     */
    const hangup = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "hangup" }));
        }
        setState((prev) => ({ ...prev, phase: "ended" }));
    }, []);

    /**
     * Cleanup on unmount
     */
    useEffect(() => {
        return () => {
            wsRef.current?.close();
        };
    }, []);

    return {
        ...state,
        startCall,
        joinCall,
        sendResponse,
        hangup,
        isConnected: wsRef.current?.readyState === WebSocket.OPEN,
    };
}
