import "../style/app.css";
import { StreamClientScrcpy } from "./googDevice/client/StreamClientScrcpy";

import { MsePlayer } from "./player/MsePlayer";

window.onload = async function (): Promise<void> {
  StreamClientScrcpy.registerPlayer(MsePlayer);

  const mainUrlParams = new URLSearchParams(window.location.search);
  const password = mainUrlParams.get("password");

  let wsPath: string;
  const fullPath = window.location.pathname;

  if (fullPath.startsWith("/desktop/")) {
    console.log("Path starts with '/desktop/'. Applying specific path logic.");
    const pathParts = fullPath.split("/").filter((p) => p);
    if (pathParts.length >= 2) {
      wsPath = `/${pathParts[0]}/${pathParts[1]}`;
    } else {
      wsPath = `/${pathParts.join("/")}`;
    }
  } else {
    console.log(
      "Path does not start with '/desktop/'. Applying generic path logic.",
    );
    wsPath = fullPath;
    const lastSlashIndex = wsPath.lastIndexOf("/");
    if (lastSlashIndex > 0) {
      wsPath = wsPath.substring(0, lastSlashIndex);
    }
  }

  const params = new URLSearchParams();

  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsHost = window.location.host;

  const udid = "emulator-5554";
  const player = "mse";
  const scrcpyListenPort = 8886;

  const internalWsParams = new URLSearchParams();
  internalWsParams.set("action", "proxy-adb");
  internalWsParams.set("remote", `tcp:${scrcpyListenPort}`);
  internalWsParams.set("udid", udid);

  if (password) {
    internalWsParams.set("password", password);
    console.log(
      "Password parameter found and will be added to the WebSocket URL.",
    );
  } else {
    console.warn('No "password" parameter found in the main URL.');
  }

  const wsUrlValue = `${wsProtocol}//${wsHost}${wsPath}?${internalWsParams.toString()}`;

  params.set("action", StreamClientScrcpy.ACTION);
  params.set("udid", udid);
  params.set("player", player);
  params.set("ws", wsUrlValue);

  console.log(
    `Starting StreamClientScrcpy via proxy. Calculated WS URL: ${wsUrlValue}`,
  );
  StreamClientScrcpy.start(params);
};
