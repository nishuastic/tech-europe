import { McpServer } from "skybridge/server";
import { z } from "zod";

const server = new McpServer(
  {
    name: "admin-hero-skybridge",
    version: "1.0.0",
  },
  { capabilities: {} },
).registerWidget(
  "admin-hero",
  {
    description: "Admin Hero - French Bureaucracy Assistant",
  },
  {
    description: "Use this to get expert explanations and email drafts for French administrative tasks.",
    inputSchema: {
      message: z.string().describe("The user's question about French administration."),
    },
  },
  async ({ message }) => {
    try {
      // usage: BACKEND_URL=https://your-ngrok.app
      const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";


      // Call the backend
      const response = await fetch(`${BACKEND_URL}/api/v1/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      // data: { transcript, explanation, email_draft, conversation_id }

      return {
        structuredContent: data,
        content: [{ type: "text", text: data.explanation }],
        isError: false,
      };
    } catch (error) {
      return {
        content: [{ type: "text", text: `Error: ${error}` }],
        isError: true,
      };
    }
  },
).registerWidget(
  "call-french-admin",
  {
    description: "Call French Administration (CAF, Prefecture, etc.)",
  },
  {
    description: "Use this to call a French administration hotline on behalf of the user.",
    inputSchema: {
      target: z.enum(["caf", "prefecture", "impots"]).describe("The agency to call."),
      message: z.string().describe("The user's initial message or question to the agency."),
    },
  },
  async ({ target, message }) => {
    try {
      const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

      // Start the call session on the backend
      const response = await fetch(`${BACKEND_URL}/api/v1/call/initiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, message }),
      });

      if (!response.ok) {
        throw new Error(`Failed to start call: ${response.statusText}`);
      }

      const data = await response.json();
      // data: { status, message, call_action: { call_id, target, status } }

      return {
        structuredContent: data.call_action,
        content: [{ type: "text", text: data.message }],
        isError: false,
      };
    } catch (error) {
      return {
        content: [{ type: "text", text: `Error starting call: ${error}` }],
        isError: true,
      };
    }
  },
);

export default server;
export type AppType = typeof server;
