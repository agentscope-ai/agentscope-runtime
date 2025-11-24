// src/index.ts

import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { server } from './server.js';
import { initializeAdb } from './adb-tool.js';

async function main() {
  await initializeAdb();

  const transport = new StdioServerTransport();
  process.on('SIGINT', () => {
    console.log('Caught interrupt signal, shutting down.');
    transport.close();
    process.exit(0);
  });
  
  await server.connect(transport);
  console.error('ADB MCP server running on stdio');

}

main().catch(console.error);
