// src/server.ts

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
	CallToolRequestSchema,
	ListToolsRequestSchema,
	type Tool,
} from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import * as adb from './adb-tool.js';

import { zodToJsonSchema } from 'zod-to-json-schema';


const adbToolParams = z.discriminatedUnion('action', [
  z.object({
    action: z.literal('get_screen_resolution'),
  }).describe("Get the physical screen resolution of the device."),

  z.object({
    action: z.literal('tap'),
    coordinate: z.tuple([z.number().int(), z.number().int()])
    .describe("The [x, y] pixel coordinates on the screen to tap."),
  }).describe("Simulate a single tap on the screen at a specified coordinate."),

  z.object({
    action: z.literal('swipe'),
    start: z.tuple([z.number().int(), z.number().int()])
    .describe("The starting [x, y] pixel coordinates of the swipe."),
    end: z.tuple([z.number().int(), z.number().int()])
    .describe("The ending [x, y] pixel coordinates of the swipe."),
    duration: z.number().int().optional()
    .describe("The duration of the swipe in milliseconds (optional, defaults to 300ms)."),
  }).describe("Simulate a swipe gesture on the screen from a start to an end coordinate."),

  z.object({
    action: z.literal('input_text'),
    text: z.string().describe("The text to be typed into the focused input field."),
  }).describe("Input a string of text. A text field must be focused on the device screen first."),

  z.object({
    action: z.literal('key_event'),
    code: z.union([z.number().int(), z.string().regex(/^\d+$/).transform(Number)])
    .describe("The key code to send. Common codes: 3 (Home), 4 (Back), 66 (Enter)."),
  }).describe("Send a key event to the device, simulating a button press."),

  // get_screenshot
  z.object({
    action: z.literal('get_screenshot'),
  }).describe("Take a screenshot of the current device screen and return it as a Base64 encoded PNG image."),
]);


const legacyAdbTool = {
  name: 'adb', 
  description: 'A tool to control an Android device using the Android Debug Bridge (ADB).',
  
  inputSchema: {
    properties: {
      action: {
        type: 'string',
        description: 'The specific action to perform.'
      },
      coordinate: { type: 'array', description: 'For "tap" action.' },
      start: { type: 'array', description: 'For "swipe" action.' },
      end: { type: 'array', description: 'For "swipe" action.' },
      duration: { type: 'number', description: 'For "swipe" action (optional).' },
      text: { type: 'string', description: 'For "input_text" action.' },
      code: { type: 'string | number', description: 'For "key_event" action.' }
    },
    required: ['action'],
  },
};




class InvalidToolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'InvalidToolError';
  }
}

export const server = new Server({
	name: 'mobile-use-mcp',
	version: '0.0.1',
}, {
	capabilities: {
		tools: {},
	},
});

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [legacyAdbTool], 
  };
});

server.setRequestHandler(
  CallToolRequestSchema,  
  async (request) => {
    const { name, arguments: args } = request.params;

    if (name !== 'adb') { 
      throw new InvalidToolError(`Tool '${name}' not supported. Only 'adb' is available.`);
    }

    try {
      const validatedArgs = adbToolParams.parse(args);

      switch (validatedArgs.action) {
        case 'get_screen_resolution': {
          const resolution = await adb.getScreenResolution();
          return { content: [{ type: 'text', text: JSON.stringify(resolution) }] };
        }
        case 'tap': {
          const [x, y] = validatedArgs.coordinate;
          const result = await adb.tap(x, y);
          return { content: [{ type: 'text', text: result }] };
        }
        case 'swipe': {
          const [startX, startY] = validatedArgs.start;
          const [endX, endY] = validatedArgs.end;
          const result = await adb.swipe(startX, startY, endX, endY, validatedArgs.duration);
          return { content: [{ type: 'text', text: result }] };
        }
        case 'input_text': {
          const result = await adb.inputText(validatedArgs.text);
          return { content: [{ type: 'text', text: result }] };
        }
        case 'key_event': {
          const result = await adb.keyEvent(validatedArgs.code);
          return { content: [{ type: 'text', text: result }] };
        }
		case 'get_screenshot': {
        const base64Image = await adb.getScreenshot();
        return {
          content: [{
            type: 'image',
            data: base64Image,
            mimeType: 'image/png'
          }]
        };
      }
      }
    } catch (error) {
      if (error instanceof z.ZodError) {
        throw new InvalidToolError(`Invalid arguments for tool '${name}': ${error.message}`);
      }
      throw error;
    }
  }
);
