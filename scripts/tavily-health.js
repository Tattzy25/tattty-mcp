import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const serverUrl =
  "https://mcp.zapier.com/api/mcp/s/NmRlMTdiMmQtYzRmYi00NDQ5LTlmYWMtN2NjM2JlNWMzYzhhOjVmNzEyYmZmLWJjNGQtNGQ1NS1hMGQwLTVjMGJjNmYwYzBmMg==/mcp";
const query =
  process.argv[2] ||
  "Railway.app health check requirements readiness probes steady 200 responses";

async function main() {
  const client = new Client(
    { name: "tattty-mcp-railway-research", version: "1.0.0" },
    { capabilities: {} }
  );

  const transport = new StreamableHTTPClientTransport(new URL(serverUrl));

  console.log("Connecting to Tavily MCP server...");
  await client.connect(transport);
  console.log("Connected.");

  const tools = await client.listTools();
  console.log(`Discovered ${tools.tools.length} tools.`);
  const hasTavily = tools.tools.some((tool) => tool.name === "tavily_search");
  if (!hasTavily) {
    throw new Error("tavily_search tool not advertised by server");
  }

  console.log("Querying tavily_search with:", query);
  const result = await client.callTool({
    name: "tavily_search",
    arguments: {
      instructions:
        "Investigate Railway platform HTTP health check expectations for MCP deployment",
      query,
      topic: "railway app health checks",
      include_answer: "true",
      include_raw_content: "true",
    },
  });

  console.log("tavily_search result:\n", JSON.stringify(result, null, 2));

  await client.transport?.close();
  await client.close();
  console.log("Disconnected.");
}

main().catch((error) => {
  console.error("Tavily research failed:", error);
  process.exit(1);
});
