import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
  Tool,
  TextContent,
} from "@modelcontextprotocol/sdk/types.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { chromium, Browser, Page } from "playwright";

interface NavigateInput {
  url: string;
}

interface ClickInput {
  selector: string;
}

interface FillFormInput {
  fields: Record<string, string>;
}

interface ScreenshotInput {
  fullPage?: boolean;
}

interface GetTextInput {
  selector: string;
}

interface EvaluateInput {
  script: string;
}

type ToolInput =
  | NavigateInput
  | ClickInput
  | FillFormInput
  | ScreenshotInput
  | GetTextInput
  | EvaluateInput;

class PlaywrightMCPServer {
  private server: Server;
  private browser: Browser | null = null;
  private page: Page | null = null;

  constructor() {
    this.server = new Server({
      name: "playwright-mcp",
      version: "0.1.0",
    });

    this.setupHandlers();
  }

  private setupHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
      tools: this.getTools(),
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) =>
      this.handleToolCall(request)
    );
  }

  private getTools(): Tool[] {
    return [
      {
        name: "navigate",
        description:
          "Navigate to a URL in the browser. Opens the URL and waits for the page to load.",
        inputSchema: {
          type: "object" as const,
          properties: {
            url: {
              type: "string",
              description: "The URL to navigate to (e.g., https://example.com)",
            },
          },
          required: ["url"],
        },
      },
      {
        name: "click",
        description:
          "Click an element on the page by CSS selector. Waits for the element to be visible before clicking.",
        inputSchema: {
          type: "object" as const,
          properties: {
            selector: {
              type: "string",
              description:
                "CSS selector for the element to click (e.g., '#submit-btn', '.menu-item')",
            },
          },
          required: ["selector"],
        },
      },
      {
        name: "fill_form",
        description:
          "Fill form fields (input, textarea) with values. Supports multiple fields at once.",
        inputSchema: {
          type: "object" as const,
          properties: {
            fields: {
              type: "object",
              description:
                "Object mapping CSS selectors to values (e.g., {'#username': 'john', '#password': 'secret'})",
              additionalProperties: { type: "string" },
            },
          },
          required: ["fields"],
        },
      },
      {
        name: "screenshot",
        description:
          "Take a screenshot of the current page and return as base64-encoded PNG.",
        inputSchema: {
          type: "object" as const,
          properties: {
            fullPage: {
              type: "boolean",
              description:
                "If true, capture the full page. If false, capture only the viewport. Default: false",
            },
          },
          required: [],
        },
      },
      {
        name: "get_text",
        description:
          "Extract text content from element(s) by CSS selector. Returns an array of text strings.",
        inputSchema: {
          type: "object" as const,
          properties: {
            selector: {
              type: "string",
              description:
                "CSS selector for the element(s) to extract text from (e.g., '.result', 'p')",
            },
          },
          required: ["selector"],
        },
      },
      {
        name: "evaluate",
        description:
          "Execute JavaScript code in the context of the page and return the result.",
        inputSchema: {
          type: "object" as const,
          properties: {
            script: {
              type: "string",
              description:
                "JavaScript code to execute (e.g., 'document.title' or 'fetch(url).then(r => r.json())')",
            },
          },
          required: ["script"],
        },
      },
    ];
  }

  private async ensureBrowser(): Promise<void> {
    if (!this.browser) {
      this.browser = await chromium.launch({ headless: true });
    }
    if (!this.page) {
      this.page = await this.browser.newPage();
    }
  }

  private async handleToolCall(request: {
    params: { name: string; arguments?: ToolInput };
  }): Promise<{ content: TextContent[] }> {
    try {
      await this.ensureBrowser();

      const { name, arguments: args } = request.params;
      const typedArgs = args as ToolInput;

      let result: string;

      switch (name) {
        case "navigate":
          result = await this.navigate(typedArgs as NavigateInput);
          break;
        case "click":
          result = await this.click(typedArgs as ClickInput);
          break;
        case "fill_form":
          result = await this.fillForm(typedArgs as FillFormInput);
          break;
        case "screenshot":
          result = await this.screenshot(typedArgs as ScreenshotInput);
          break;
        case "get_text":
          result = await this.getText(typedArgs as GetTextInput);
          break;
        case "evaluate":
          result = await this.evaluate(typedArgs as EvaluateInput);
          break;
        default:
          result = JSON.stringify({
            success: false,
            error: `Unknown tool: ${name}`,
          });
      }

      return {
        content: [
          {
            type: "text",
            text: result,
          },
        ],
      };
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : String(error);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              success: false,
              error: errorMessage,
            }),
          },
        ],
      };
    }
  }

  private async navigate(input: NavigateInput): Promise<string> {
    if (!this.page) throw new Error("Page not initialized");

    const response = await this.page.goto(input.url, { waitUntil: "load" });
    const status = response?.status() || 0;

    return JSON.stringify({
      success: status >= 200 && status < 300,
      status,
      url: this.page.url(),
      title: await this.page.title(),
    });
  }

  private async click(input: ClickInput): Promise<string> {
    if (!this.page) throw new Error("Page not initialized");

    await this.page.click(input.selector);

    return JSON.stringify({
      success: true,
      message: `Clicked element: ${input.selector}`,
    });
  }

  private async fillForm(input: FillFormInput): Promise<string> {
    if (!this.page) throw new Error("Page not initialized");

    const results: Record<string, boolean> = {};

    for (const [selector, value] of Object.entries(input.fields)) {
      try {
        await this.page.fill(selector, value);
        results[selector] = true;
      } catch (error) {
        results[selector] = false;
      }
    }

    const allSuccess = Object.values(results).every((v) => v);

    return JSON.stringify({
      success: allSuccess,
      filled: results,
    });
  }

  private async screenshot(input: ScreenshotInput): Promise<string> {
    if (!this.page) throw new Error("Page not initialized");

    const buffer = await this.page.screenshot({
      fullPage: input.fullPage ?? false,
    });
    const base64 = buffer.toString("base64");

    return JSON.stringify({
      success: true,
      image: `data:image/png;base64,${base64}`,
      size: buffer.length,
    });
  }

  private async getText(input: GetTextInput): Promise<string> {
    if (!this.page) throw new Error("Page not initialized");

    const elements = await this.page.$$(input.selector);
    const texts: string[] = [];

    for (const element of elements) {
      const text = await element.textContent();
      if (text) {
        texts.push(text.trim());
      }
    }

    return JSON.stringify({
      success: true,
      count: texts.length,
      texts,
    });
  }

  private async evaluate(input: EvaluateInput): Promise<string> {
    if (!this.page) throw new Error("Page not initialized");

    const result = await this.page.evaluate((script) => {
      // eslint-disable-next-line no-eval
      return eval(script);
    }, input.script);

    return JSON.stringify({
      success: true,
      result,
    });
  }

  async start(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error("Playwright MCP server started");
  }

  async cleanup(): Promise<void> {
    if (this.browser) {
      await this.browser.close();
    }
  }
}

const server = new PlaywrightMCPServer();
server.start().catch(console.error);

process.on("SIGINT", async () => {
  await server.cleanup();
  process.exit(0);
});

process.on("SIGTERM", async () => {
  await server.cleanup();
  process.exit(0);
});
