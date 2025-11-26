# agentscope-runtime-starter-webui

## node version

> =22

## install

```
$ npm run install
```

## dev

```
$ npm run dev
```

## build

```
$ npm run build
```

## Core Code
```tsx
import { AgentScopeRuntimeWebUI } from '@agentscope-ai/chat';

const options = {
  theme: {
    colorPrimary: '#615CED',
    darkMode: true,
    prefix: 'agentscope-runtime-webui',
    leftHeader: {
      logo: 'https://img.alicdn.com/imgextra/i2/O1CN01lmoGYn1kjoXATy4PX_!!6000000004720-2-tps-200-200.png',
      title: 'Runtime WebUI',
    },
  },
  sender: {
    maxLength: 10000,
    disclaimer:
      'AI can also make mistakes, so please check carefully and use it with caution',
  },

  welcome: {
    greeting: 'Hello, how can I help you today?',
    description:
      'I am a helpful assistant that can help you with your questions.',
    avatar:
      'https://img.alicdn.com/imgextra/i2/O1CN01lmoGYn1kjoXATy4PX_!!6000000004720-2-tps-200-200.png',
    prompts: [
      {
        value: 'Hello',
      },
      {
        value: 'How are you?',
      },
      {
        value: 'What can you do?',
      },
    ],
  },
  api: {
    baseURL: 'YOUR_API_URL',
    token: 'YOUR_API_TOKEN', // is not required
  },
};


<AgentScopeRuntimeWebUI
  options={options}
/>


```