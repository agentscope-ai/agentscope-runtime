// src/adb-tool.ts

import Adb from 'adbkit';

const client: Adb.Client = Adb.createClient();


let deviceId: string;

export async function initializeAdb(): Promise<void> {
  try {
    const deviceDescriptors = await client.listDevices();

    if (deviceDescriptors.length === 0) {
      throw new Error('No Android devices found. Please connect a device or start an emulator.');
    }

    
    const firstDeviceDesc = deviceDescriptors[0]!;

    
    deviceId = firstDeviceDesc.id;

    console.error('Found devices:', deviceDescriptors.map(d => d.id));
    console.error(`Connected to device: ${deviceId} (${firstDeviceDesc.type})`);

  } catch (err) {
    console.error('Failed to initialize ADB:', err);
    process.exit(1); 
  }
}


function ensureDeviceId(): string {
  if (!deviceId) {
    throw new Error('ADB device ID is not initialized. Call initializeAdb() first.');
  }
  return deviceId;
}


export async function tap(x: number, y: number): Promise<string> {
  const id = ensureDeviceId();
  await client.shell(id, `input tap ${x} ${y}`);
  return `Tapped at (${x}, ${y})`;
}

export async function swipe(startX: number, startY: number, endX: number, endY: number, durationMs: number = 300): Promise<string> {
  const id = ensureDeviceId();
  await client.shell(id, `input swipe ${startX} ${startY} ${endX} ${endY} ${durationMs}`);
  return `Swiped from (${startX}, ${startY}) to (${endX}, ${endY})`;
}

export async function inputText(text: string): Promise<string> {
  const id = ensureDeviceId();
  const escapedText = text.replace(/'/g, "'\\''");
  await client.shell(id, `input text '${escapedText}'`);
  return `Input text: ${text}`;
}

export async function keyEvent(keyCode: number | string): Promise<string> {
  const id = ensureDeviceId();
  await client.shell(id, `input keyevent ${keyCode}`);
  return `Sent key event: ${keyCode}`;
}

export async function getScreenResolution(): Promise<{ width: number, height: number }> {
  const id = ensureDeviceId();
  const output = await client.shell(id, 'wm size');
  const outputStr = await streamToString(output);
  
  const match = outputStr.match(/Physical size: (\d+)x(\d+)/);
  if (match && match[1] && match[2]) {
    return {
      width: parseInt(match[1], 10),
      height: parseInt(match[2], 10),
    };
  }
  throw new Error('Could not determine screen resolution from ADB output.');
}

/**
 * @returns {Promise<string>} -  Base64 
 */
export async function getScreenshot(): Promise<string> {
  const id = ensureDeviceId();
  
  const stream = await client.screencap(id);

  const chunks: Buffer[] = [];
  return new Promise((resolve, reject) => {
    stream.on('data', (chunk: Buffer) => chunks.push(chunk));
    stream.on('error', (err) => reject(err));
    stream.on('end', () => {
      resolve(Buffer.concat(chunks).toString('base64'));
    });
  });
}

async function streamToString(stream: NodeJS.ReadableStream): Promise<string> {
    const chunks: Buffer[] = [];
    return new Promise((resolve, reject) => {
        stream.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
        stream.on('error', (err) => reject(err));
        stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    });
}
