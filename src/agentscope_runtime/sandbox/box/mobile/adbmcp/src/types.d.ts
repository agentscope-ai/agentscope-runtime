// src/types.d.ts

declare module 'adbkit' {
  namespace Adb {
    interface Device {
      id: string;
      type: 'device' | 'emulator' | 'offline';
    }

    /**
     */
    interface Client {
      /**
       */
      listDevices(): Promise<Device[]>;

      /**
       */
      shell(id: string, command: string | string[]): Promise<NodeJS.ReadableStream>;
      /**
       */
      screencap(id: string): Promise<NodeJS.ReadableStream>;

    }

    function createClient(options?: { host?: string; port?: number }): Client;
  }

  export = Adb;
}
