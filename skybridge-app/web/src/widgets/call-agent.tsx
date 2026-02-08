import "@/index.css";
import { mountWidget } from "skybridge/web";
import { useToolInfo } from "../helpers";
import { useCallSession } from "../hooks/useCallSession";
import { useEffect, useRef, useState } from "react";
import {
    PhoneOff,
    Send,
    Loader2,
    User,
    Building,
    Phone,
} from "lucide-react";

function CallAgentWidget() {
    const { output } = useToolInfo<"call-french-admin">();

    // safe cast to access potential backend_url
    const outputData = output?.structuredContent as any;
    const backendUrl = outputData?.backend_url || "http://localhost:8000";

    const {
        callId,
        phase,
        target,
        transcript,
        waitingForUser,
        error,
        agentThinking,
        agentSuggestion,
        joinCall,
        sendResponse,
        hangup,
        isConnected,
    } = useCallSession(backendUrl);

    const [userInput, setUserInput] = useState("");
    const transcriptRef = useRef<HTMLDivElement>(null);
    const hasJoined = useRef(false);

    // Auto-join when widget loads with callId
    useEffect(() => {
        if (output && !output.isError && output.structuredContent) {
            const data = output.structuredContent as any;
            console.log("[CallAgentWidget] Output received:", data);
            console.log("[CallAgentWidget] Backend URL:", backendUrl);
            if (data.call_id && !callId && !hasJoined.current) {
                hasJoined.current = true;
                console.log("[CallAgentWidget] Joining call:", data.call_id, "target:", data.target);
                joinCall(data.call_id, data.target || "caf");
            } else if (data.call_action?.call_id && !callId && !hasJoined.current) {
                // Handle nested call_action from backend
                hasJoined.current = true;
                const action = data.call_action;
                console.log("[CallAgentWidget] Joining call (from action):", action.call_id, "target:", action.target);
                joinCall(action.call_id, action.target || "caf");
            }
        }
    }, [output, callId, joinCall, backendUrl]);

    // Auto-scroll transcript
    useEffect(() => {
        if (transcriptRef.current) {
            transcriptRef.current.scrollTo({
                top: transcriptRef.current.scrollHeight,
                behavior: "smooth"
            });
        }
    }, [transcript, agentThinking, agentSuggestion, phase]);

    const handleSendResponse = () => {
        if (userInput.trim()) {
            sendResponse(userInput);
            setUserInput("");
        }
    };

    // Debug output
    useEffect(() => {
        console.log("CallAgentWidget output:", output);
        console.log("CallAgentWidget state - phase:", phase, "callId:", callId, "transcript:", transcript.length);
    }, [output, phase, callId, transcript]);

    if (!output) return <div style={{ padding: "20px", color: "#6b7280" }}>Initializing call interface...</div>;

    // Fix type error for output.content
    if (output.isError) {
        const content = output.content as any[];
        return (
            <div style={{
                padding: "20px",
                color: "#ef4444",
                backgroundColor: "#fee2e2",
                borderRadius: "8px",
                border: "1px solid #fecaca"
            }}>
                Error: {content?.[0]?.text || "Unknown error"}
            </div>
        );
    }

    const getStatusText = () => {
        switch (phase) {
            case "gathering_info": return "Initializing...";
            case "ready_to_call": return "Ready to call";
            case "dialing": return `Calling ${target.toUpperCase()}...`;
            case "connected": return "Connected";
            case "caf_speaking": return `${target.toUpperCase()} is speaking...`;
            case "waiting_user": return "Your turn to respond";
            case "user_speaking": return `Speaking to ${target.toUpperCase()}...`;
            case "ended": return "Call ended";
            case "failed": return "Call failed";
            default: return (phase as string).replace("_", " ");
        }
    };

    const isCallActive = [
        "dialing",
        "connected",
        "caf_speaking",
        "waiting_user",
        "user_speaking",
    ].includes(phase);

    // Enhanced styles
    const styles = {
        container: {
            display: "flex",
            flexDirection: "column" as const,
            height: "600px",
            maxHeight: "80vh",
            backgroundColor: "#111827", // gray-900
            borderRadius: "1rem",
            border: "1px solid #1f2937", // gray-800
            overflow: "hidden",
            color: "white",
            fontFamily: "system-ui, -apple-system, sans-serif",
            boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.5)",
        },
        header: {
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "1rem 1.5rem",
            borderBottom: "1px solid #1f2937",
            backgroundColor: "#030712", // gray-950
        },
        statusBadge: {
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.25rem 0.75rem",
            borderRadius: "9999px",
            backgroundColor: isCallActive ? "rgba(34, 197, 94, 0.1)" : phase === "ended" ? "rgba(107, 114, 128, 0.1)" : "rgba(234, 179, 8, 0.1)",
            color: isCallActive ? "#4ade80" : phase === "ended" ? "#9ca3af" : "#facc15",
            fontSize: "0.75rem",
            fontWeight: 600,
            border: "1px solid",
            borderColor: isCallActive ? "rgba(34, 197, 94, 0.2)" : phase === "ended" ? "rgba(107, 114, 128, 0.2)" : "rgba(234, 179, 8, 0.2)",
        },
        statusDot: {
            width: "0.5rem",
            height: "0.5rem",
            borderRadius: "50%",
            backgroundColor: "currentColor",
        },
        transcript: {
            flex: 1,
            padding: "1.5rem",
            overflowY: "auto" as const,
            display: "flex",
            flexDirection: "column" as const,
            gap: "1.5rem",
            backgroundColor: "#111827",
        },
        inputArea: {
            padding: "1.5rem",
            borderTop: "1px solid #1f2937",
            backgroundColor: "#030712",
            display: "flex",
            gap: "0.75rem",
        },
        input: {
            flex: 1,
            padding: "0.75rem 1rem",
            borderRadius: "0.5rem",
            border: "1px solid #374151",
            backgroundColor: "#1f2937",
            color: "white",
            fontSize: "0.875rem",
            outline: "none",
            transition: "border-color 0.2s",
        },
        button: {
            padding: "0.75rem 1rem",
            borderRadius: "0.5rem",
            cursor: "pointer",
            border: "none",
            backgroundColor: "#2563eb",
            color: "white",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "background-color 0.2s",
        },
        hangupButton: {
            padding: "0.5rem 1rem",
            borderRadius: "0.5rem",
            cursor: "pointer",
            border: "1px solid #ef4444",
            backgroundColor: "transparent",
            color: "#ef4444",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            fontSize: "0.875rem",
            fontWeight: 500,
            transition: "all 0.2s",
        },
        bubble: {
            display: "flex",
            gap: "1rem",
            maxWidth: "85%",
        },
        bubbleContent: {
            padding: "1rem",
            borderRadius: "1rem",
            fontSize: "0.9375rem",
            lineHeight: "1.5",
            boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
        },
        agentThinking: {
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            color: "#60a5fa",
            fontSize: "0.875rem",
            padding: "1rem",
            backgroundColor: "rgba(37, 99, 235, 0.1)",
            borderRadius: "0.75rem",
            border: "1px solid rgba(37, 99, 235, 0.2)",
            animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        },
        agentSuggestion: {
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            color: "#4ade80",
            fontSize: "0.875rem",
            padding: "1rem",
            backgroundColor: "rgba(22, 163, 74, 0.1)",
            borderRadius: "0.75rem",
            border: "1px solid rgba(22, 163, 74, 0.2)",
        },
        emptyState: {
            display: "flex",
            flexDirection: "column" as const,
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            color: "#6b7280",
            gap: "1rem",
        }
    };

    return (
        <div style={styles.container}>
            {/* Header */}
            <div style={styles.header}>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                    <div style={{
                        width: "2.5rem",
                        height: "2.5rem",
                        borderRadius: "0.75rem",
                        backgroundColor: isCallActive ? "#166534" : "#1f2937",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: isCallActive ? "#4ade80" : "#9ca3af",
                    }}>
                        <Phone size={20} />
                    </div>
                    <div>
                        <h3 style={{ margin: 0, fontSize: "1.125rem", fontWeight: 600, letterSpacing: "-0.025em" }}>
                            {isCallActive ? `Live Call: ${target.toUpperCase()}` : "Bureaucracy Buddy"}
                        </h3>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.25rem" }}>
                            <div style={styles.statusBadge}>
                                <div style={styles.statusDot} />
                                {getStatusText()}
                            </div>
                        </div>
                    </div>
                </div>
                {isCallActive && (
                    <button
                        onClick={hangup}
                        style={styles.hangupButton}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.backgroundColor = "#ef4444";
                            e.currentTarget.style.color = "white";
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.backgroundColor = "transparent";
                            e.currentTarget.style.color = "#ef4444";
                        }}
                    >
                        <PhoneOff size={16} />
                        Hang Up
                    </button>
                )}
            </div>

            {/* Transcript */}
            <div ref={transcriptRef} style={styles.transcript}>
                {(transcript.length === 0 && (phase === "dialing" || phase === "gathering_info")) && (
                    <div style={styles.emptyState}>
                        <div style={{ position: "relative" }}>
                            <div style={{
                                position: "absolute",
                                inset: 0,
                                borderRadius: "50%",
                                backgroundColor: "#2563eb",
                                opacity: 0.2,
                                animation: "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite",
                            }} />
                            <div style={{
                                position: "relative",
                                padding: "1rem",
                                borderRadius: "50%",
                                backgroundColor: "rgba(37, 99, 235, 0.1)",
                                color: "#3b82f6",
                            }}>
                                <Phone size={32} />
                            </div>
                        </div>
                        <p style={{ fontSize: "1rem", fontWeight: 500 }}>
                            {phase === "gathering_info" ? "Preparing call..." : `Calling ${target.toUpperCase()}...`}
                        </p>
                        <p style={{ fontSize: "0.875rem" }}>
                            {phase === "gathering_info" ? "Initializing connection..." : "Please wait while we connect you."}
                        </p>
                    </div>
                )}

                {transcript.map((entry, idx) => {
                    const isUser = entry.speaker === "user";
                    return (
                        <div key={idx} style={{
                            ...styles.bubble,
                            alignSelf: isUser ? "flex-end" : "flex-start",
                            flexDirection: isUser ? "row-reverse" : "row",
                        }}>
                            <div style={{
                                width: "2.5rem",
                                height: "2.5rem",
                                borderRadius: "50%",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                backgroundColor: isUser ? "#2563eb" : "#c2410c", // blue-600 : orange-700
                                boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                                flexShrink: 0,
                                color: "white",
                            }}>
                                {isUser ? <User size={18} /> : <Building size={18} />}
                            </div>
                            <div style={{
                                ...styles.bubbleContent,
                                backgroundColor: isUser ? "#2563eb" : "#374151", // blue-600 : gray-700
                                color: "white",
                                borderTopRightRadius: isUser ? "0.25rem" : "1rem",
                                borderTopLeftRadius: isUser ? "1rem" : "0.25rem",
                            }}>
                                <p style={{ margin: 0 }}>{entry.english}</p>
                                {entry.french && !isUser && (
                                    <p style={{ margin: "0.5rem 0 0 0", fontSize: "0.8125rem", color: "#d1d5db", fontStyle: "italic", borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: "0.5rem" }}>
                                        "{entry.french}"
                                    </p>
                                )}
                            </div>
                        </div>
                    );
                })}

                {phase === "caf_speaking" && (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", color: "#9ca3af", fontSize: "0.875rem", paddingLeft: "3.5rem" }}>
                        <div style={{ display: "flex", gap: "0.25rem" }}>
                            <div style={{ width: "0.25rem", height: "0.25rem", backgroundColor: "currentColor", borderRadius: "50%", animation: "bounce 1s infinite" }} />
                            <div style={{ width: "0.25rem", height: "0.25rem", backgroundColor: "currentColor", borderRadius: "50%", animation: "bounce 1s infinite 0.1s" }} />
                            <div style={{ width: "0.25rem", height: "0.25rem", backgroundColor: "currentColor", borderRadius: "50%", animation: "bounce 1s infinite 0.2s" }} />
                        </div>
                        {target.toUpperCase()} is speaking...
                    </div>
                )}

                {agentThinking && (
                    <div style={styles.agentThinking}>
                        <Loader2 size={18} className="animate-spin" />
                        <span>Agent is thinking...</span>
                    </div>
                )}

                {agentSuggestion && phase === "user_speaking" && (
                    <div style={styles.agentSuggestion}>
                        <User size={18} />
                        <div>
                            <span style={{ fontWeight: 600 }}>Suggested Response:</span> "{agentSuggestion}"
                        </div>
                    </div>
                )}
            </div>

            {/* Error display */}
            {error && (
                <div style={{
                    margin: "0 1.5rem 1.5rem 1.5rem",
                    padding: "1rem",
                    backgroundColor: "rgba(127, 29, 29, 0.5)",
                    border: "1px solid #7f1d1d",
                    borderRadius: "0.75rem",
                    color: "#fca5a5",
                    fontSize: "0.875rem",
                }}>
                    {error}
                </div>
            )}

            {/* Debug Info (Auto-hidden unless error or manual toggle) */}
            <div style={{
                padding: "0.5rem 1.5rem",
                fontSize: "0.75rem",
                color: "#4b5563",
                borderTop: "1px solid #1f2937",
                display: "flex",
                justifyContent: "space-between"
            }}>
                <span>Status: {isConnected ? "🟢 Connected" : "🔴 Disconnected"}</span>
                <span>ID: {callId ? callId.slice(0, 8) : "None"}</span>
                <span>Phase: {phase}</span>
                <span>WaitUser: {waitingForUser ? "Yes" : "No"}</span>
            </div>

            {/* Input Area */}
            {(waitingForUser || true) && (
                <div style={{
                    ...styles.inputArea,
                    display: waitingForUser ? "flex" : "none" // Only hide via display, allow rendering to check props
                }}>
                    <input
                        style={styles.input}
                        value={userInput}
                        onChange={(e) => setUserInput(e.target.value)}
                        placeholder={phase === "waiting_user" ? "Type your response..." : "Waiting for your turn..."}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" && !e.shiftKey) {
                                e.preventDefault();
                                handleSendResponse();
                            }
                        }}
                        autoFocus
                    />
                    <button
                        onClick={handleSendResponse}
                        disabled={!userInput.trim()}
                        style={{
                            ...styles.button,
                            backgroundColor: !userInput.trim() ? "#374151" : "#2563eb",
                            opacity: !userInput.trim() ? 0.5 : 1,
                            cursor: !userInput.trim() ? "not-allowed" : "pointer",
                        }}
                    >
                        <Send size={18} />
                    </button>
                </div>
            )}
        </div>
    );
}

export default CallAgentWidget;

mountWidget(<CallAgentWidget />);
