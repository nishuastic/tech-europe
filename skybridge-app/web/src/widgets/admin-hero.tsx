import "@/index.css";
import { mountWidget } from "skybridge/web";
import { useToolInfo } from "../helpers";

function AdminHeroWidget() {
    const { output } = useToolInfo<"admin-hero">();

    if (!output) {
        return (
            <div style={{ padding: '20px', textAlign: 'center', color: '#666', fontFamily: 'system-ui' }}>
                Consulting the bureaucracy...
            </div>
        );
    }

    if (output.isError) {
        return (
            <div style={{ padding: '20px', color: '#ef4444', fontFamily: 'system-ui' }}>
                Error: {String(output.content[0]?.text || "Unknown error")}
            </div>
        );
    }

    const data = output.structuredContent as any;
    const draft = data.email_draft;

    return (
        <div style={{ fontFamily: 'system-ui, -apple-system, sans-serif', padding: '16px', maxWidth: '600px' }}>
            <div style={{ marginBottom: '16px' }}>
                <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 'bold', color: '#2563eb' }}>
                    AdminHero Says:
                </h3>
                <p style={{ margin: 0, lineHeight: '1.6', color: '#1f2937' }}>
                    {data.explanation}
                </p>
            </div>

            {draft && (draft.subject || draft.body) && (
                <div style={{
                    marginTop: '20px',
                    padding: '16px',
                    backgroundColor: '#f9fafb',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px'
                }}>
                    <h4 style={{ margin: '0 0 12px 0', fontSize: '14px', textTransform: 'uppercase', color: '#6b7280', letterSpacing: '0.05em' }}>
                        Proposed Email Draft
                    </h4>

                    {draft.subject && (
                        <div style={{ marginBottom: '12px', fontWeight: '600', color: '#111827' }}>
                            Subject: {draft.subject}
                        </div>
                    )}

                    <pre style={{
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'inherit',
                        margin: 0,
                        color: '#374151',
                        fontSize: '14px'
                    }}>
                        {draft.body}
                    </pre>
                </div>
            )}
        </div>
    );
}

export default AdminHeroWidget;

mountWidget(<AdminHeroWidget />);
