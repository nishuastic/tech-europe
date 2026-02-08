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
);

export default server;
export type AppType = typeof server;
