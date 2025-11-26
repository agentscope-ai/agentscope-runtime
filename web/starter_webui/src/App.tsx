import Chat from './components/Chat';

import { createGlobalStyle } from 'antd-style';


const GlobalStyle = createGlobalStyle`
* {
  margin: 0;
  box-sizing: border-box;
}
`;

function App() {
  return <>
    <GlobalStyle />
    <Chat />
  </>
}

export default App
