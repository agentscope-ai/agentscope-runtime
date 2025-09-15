/* eslint-disable */
import React, { useEffect, useRef, useState, useCallback } from "react";
import "./Browser.scss";

interface Tab {
  id: string;
  url: string;
  title: string;
  favicon: string | null;
  ws: WebSocket | null;
  receivedFirstFrame: boolean;
  lastImageData: string | null;
  isLoading: boolean;
  frameCount: number;
  canvasRef: React.RefObject<HTMLCanvasElement>;
  containerRef: React.RefObject<HTMLDivElement>;
  currentImageWidth: number;
  currentImageHeight: number;
  reconnecting: boolean;
  intentionalClose: boolean;
  error: boolean;
}

type ConnectionStatus = "online" | "offline" | "connecting";

const defaultWidth = 1920;
const defaultHeight = 1080;

interface BrowserProps {
  webSocketUrl: string;
  activeKey?: string;
}

const Browser: React.FC<BrowserProps> = ({ webSocketUrl, activeKey }) => {
  const [tabs, setTabs] = useState<Record<string, Tab>>({});
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const [tabOrder, setTabOrder] = useState<string[]>([]);
  const [isUrlBarFocused, setIsUrlBarFocused] = useState(false);
  const urlTextRef = useRef<HTMLInputElement>(null);
  const wsDiscoveryRef = useRef<WebSocket | null>(null);
  const activeConnectionRetries = useRef<Record<string, number>>({});
  const singlePageMode = false;
  const interactive = true;

  useEffect(() => {
    if (singlePageMode) return;
    const ws = new WebSocket(webSocketUrl + "?tabInfo=true");
    wsDiscoveryRef.current = ws;
    ws.onopen = () => setConnectionStatus("online");
    ws.onclose = () => setConnectionStatus("offline");
    ws.onerror = () => setConnectionStatus("offline");
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "tabList" && payload.tabs) {
        handleTabList(payload.tabs, payload.firstTabId);
      } else if (payload.type === "tabClosed" && payload.pageId) {
        handleTabClosed(payload.pageId);
      } else if (payload.type === "activeTabChange" && payload.pageId) {
        setActiveTabId(payload.pageId);
      }
    };
    return () => ws.close();
  }, [webSocketUrl]);

  useEffect(() => {
    if (!activeTabId) return;
    const tab = tabs[activeTabId];
    if (!tab) return;
    if (tab.ws) return;
    connectTabWebSocket(activeTabId);
  }, [activeTabId, tabs]);

  const handleTabList = useCallback((tabList: any[], firstTabId?: string) => {
    const newTabs: Record<string, Tab> = {};
    const order: string[] = [];
    tabList.forEach((tab) => {
      newTabs[tab.id] = {
        id: tab.id,
        url: tab.url,
        title: tab.title,
        favicon: tab.favicon,
        ws: null,
        receivedFirstFrame: false,
        lastImageData: null,
        isLoading: false,
        frameCount: 0,
        canvasRef:
          React.createRef<HTMLCanvasElement>() as React.RefObject<HTMLCanvasElement>,
        containerRef:
          React.createRef<HTMLDivElement>() as React.RefObject<HTMLDivElement>,
        currentImageWidth: defaultWidth,
        currentImageHeight: defaultHeight,
        reconnecting: false,
        intentionalClose: false,
        error: false,
      };
      order.push(tab.id);
    });
    setTabs(newTabs);
    setTabOrder(order);
    if (firstTabId && newTabs[firstTabId]) {
      setActiveTabId(firstTabId);
    } else if (tabList.length > 0) {
      setActiveTabId(tabList[0].id);
    }
  }, []);

  const handleTabClosed = useCallback(
    (pageId: string) => {
      setTabs((prev) => {
        const updated = { ...prev };
        if (updated[pageId]?.ws) updated[pageId].ws?.close();
        delete updated[pageId];
        return updated;
      });
      setTabOrder((prev) => prev.filter((id) => id !== pageId));
      if (activeTabId === pageId) {
        const tabIds = tabOrder.filter((id) => id !== pageId);
        if (tabIds.length > 0) setActiveTabId(tabIds[0]);
        else setActiveTabId(null);
      }
    },
    [activeTabId, tabOrder],
  );

  const updateTabInfo = useCallback(
    (pageId: string, url: string, title: string, favicon: string | null) => {
      setTabs((prev) => ({
        ...prev,
        [pageId]: {
          ...prev[pageId],
          url,
          title,
          favicon,
        },
      }));
    },
    [],
  );

  const connectTabWebSocket = (pageId: string) => {
    setTabs((prev) => {
      if (!prev[pageId]) return prev;
      return {
        ...prev,
        [pageId]: {
          ...prev[pageId],
          isLoading: true,
          error: false,
          reconnecting: true,
        },
      };
    });
    const ws = new WebSocket(
      webSocketUrl + `?pageId=${encodeURIComponent(pageId)}`,
    );
    ws.onopen = () => {
      setTabs((prev) => {
        if (!prev[pageId]) return prev;
        return {
          ...prev,
          [pageId]: {
            ...prev[pageId],
            ws,
            isLoading: false,
            error: false,
            reconnecting: false,
            frameCount: 0,
          },
        };
      });
      setConnectionStatus("online");
    };
    ws.onclose = () => {
      setTabs((prev) => {
        if (!prev[pageId]) return prev;
        return {
          ...prev,
          [pageId]: {
            ...prev[pageId],
            isLoading: false,
            error: true,
            reconnecting: false,
            ws: null,
          },
        };
      });
      setConnectionStatus("offline");
    };
    ws.onerror = () => {
      setTabs((prev) => {
        if (!prev[pageId]) return prev;
        return {
          ...prev,
          [pageId]: {
            ...prev[pageId],
            isLoading: false,
            error: true,
            reconnecting: false,
          },
        };
      });
      setConnectionStatus("offline");
    };
    ws.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "tabUpdate") {
        updateTabInfo(
          pageId,
          payload.url || "",
          payload.title || "",
          payload.favicon || null,
        );
      } else if (payload.type === "targetClosed") {
        handleTabClosed(pageId);
      }
      if (payload.data) {
        renderCanvasImage(
          pageId,
          payload.data,
          payload.url,
          payload.title,
          payload.favicon,
        );
      }
    };
    setTabs((prev) => {
      if (!prev[pageId]) return prev;
      return {
        ...prev,
        [pageId]: {
          ...prev[pageId],
          ws,
        },
      };
    });
  };

  const renderCanvasImage = (
    pageId: string,
    imageData: string,
    url?: string,
    title?: string,
    favicon?: string,
  ) => {
    setTabs((prev) => {
      const updated = { ...prev };
      if (!updated[pageId]) return updated;
      updated[pageId].receivedFirstFrame = true;
      updated[pageId].lastImageData = imageData.startsWith(
        "data:image/jpeg;base64,",
      )
        ? imageData
        : `data:image/jpeg;base64,${imageData}`;
      updated[pageId].isLoading = false;
      updated[pageId].error = false;
      if (url && !isUrlBarFocused) updated[pageId].url = url;
      if (title) updated[pageId].title = title;
      if (favicon) updated[pageId].favicon = favicon;
      updated[pageId].frameCount++;
      return updated;
    });
    setTimeout(() => {
      const tab = tabs[pageId];
      const canvas = tab?.canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d", { alpha: false });
      if (!ctx) return;
      const img = new window.Image();
      img.src = imageData.startsWith("data:image/jpeg;base64,")
        ? imageData
        : `data:image/jpeg;base64,${imageData}`;
      img.onload = () => {
        setTabs((prev) => {
          const updated = { ...prev };
          if (!updated[pageId]) return updated;
          updated[pageId].currentImageWidth = img.naturalWidth;
          updated[pageId].currentImageHeight = img.naturalHeight;
          return updated;
        });
        const dpr = window.devicePixelRatio || 1;
        const container = tab?.containerRef.current;
        const targetHeight = container?.clientHeight || defaultHeight;
        const targetWidth =
          targetHeight * (img.naturalWidth / img.naturalHeight);
        canvas.width = targetWidth * dpr;
        canvas.height = targetHeight * dpr;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);
        canvas.style.height = "100%";
        canvas.style.width = "auto";
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(
          img,
          0,
          0,
          Math.floor(canvas.width / dpr),
          Math.floor(canvas.height / dpr),
        );
      };
    }, 0);
  };

  useEffect(() => {
    if (!activeTabId || activeKey !== "3") return;
    const tab = tabs[activeTabId];
    if (!tab) return;
    const canvas = tab.canvasRef.current;
    if (!canvas) return;
    // 鼠标事件
    const getScaledCoordinates = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = tab.currentImageWidth / rect.width;
      const scaleY = tab.currentImageHeight / rect.height;
      return {
        x: Math.max(
          0,
          Math.min(
            Math.round((e.clientX - rect.left) * scaleX),
            tab.currentImageWidth,
          ),
        ),
        y: Math.max(
          0,
          Math.min(
            Math.round((e.clientY - rect.top) * scaleY),
            tab.currentImageHeight,
          ),
        ),
      };
    };
    const handleMouse = (e: MouseEvent, type: string) => {
      if (!tab.ws || tab.ws.readyState !== WebSocket.OPEN) return;
      const coords = getScaledCoordinates(e);
      const modifiers =
        (e.ctrlKey ? 2 : 0) |
        (e.shiftKey ? 8 : 0) |
        (e.altKey ? 1 : 0) |
        (e.metaKey ? 4 : 0);
      let button = "none";
      if (type === "mousePressed" || type === "mouseReleased") {
        button = e.button === 0 ? "left" : e.button === 1 ? "middle" : "right";
      }

      const eventData = JSON.stringify({
        type: "mouseEvent",
        pageId: activeTabId,
        event: {
          type,
          x: coords.x,
          y: coords.y,
          button,
          modifiers,
          clickCount: (e as any).detail || 1,
        },
      });

      tab.ws.send(eventData);
    };
    let moveTimeout: any = null;
    const handleMouseMove = (e: MouseEvent) => {
      if (moveTimeout) clearTimeout(moveTimeout);
      moveTimeout = setTimeout(() => handleMouse(e, "mouseMoved"), 20);
    };
    const handleWheel = (e: WheelEvent) => {
      if (!tab.ws || tab.ws.readyState !== WebSocket.OPEN) return;
      const coords = getScaledCoordinates(e as any);
      const modifiers =
        (e.ctrlKey ? 2 : 0) |
        (e.shiftKey ? 8 : 0) |
        (e.altKey ? 1 : 0) |
        (e.metaKey ? 4 : 0);

      const eventData = JSON.stringify({
        type: "mouseEvent",
        pageId: activeTabId,
        event: {
          type: "mouseWheel",
          x: coords.x,
          y: coords.y,
          button: "none",
          modifiers,
          deltaX: e.deltaX,
          deltaY: e.deltaY,
        },
      });

      tab.ws.send(eventData);
      e.preventDefault();
    };
    canvas.addEventListener("mousedown", (e) => handleMouse(e, "mousePressed"));
    canvas.addEventListener("mouseup", (e) => handleMouse(e, "mouseReleased"));
    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("wheel", handleWheel, { passive: false });

    const handleKey = (e: KeyboardEvent, type: "keyDown" | "keyUp") => {
      if (document.activeElement === urlTextRef.current) return;
      if (!tab.ws || tab.ws.readyState !== WebSocket.OPEN) return;

      const eventData = JSON.stringify({
        type: "keyEvent",
        pageId: activeTabId,
        event: {
          type,
          text: e.key.length === 1 ? e.key : undefined,
          code: e.code,
          key: e.key,
          keyCode: e.keyCode,
        },
      });
    };
    const keydown = (e: KeyboardEvent) => handleKey(e, "keyDown");
    const keyup = (e: KeyboardEvent) => handleKey(e, "keyUp");
    document.addEventListener("keydown", keydown);
    document.addEventListener("keyup", keyup);
    return () => {
      canvas.removeEventListener("mousedown", (e) =>
        handleMouse(e, "mousePressed"),
      );
      canvas.removeEventListener("mouseup", (e) =>
        handleMouse(e, "mouseReleased"),
      );
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("wheel", handleWheel);
      document.removeEventListener("keydown", keydown);
      document.removeEventListener("keyup", keyup);
    };
  }, [activeTabId, tabs]);

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlTextRef.current || !activeTabId) return;
    const url = urlTextRef.current.value;
    handleNavigation("url", url);
    urlTextRef.current.blur();
  };

  const handleNavigation = (
    action: "back" | "forward" | "refresh" | "url",
    url?: string,
  ) => {
    if (!activeTabId || !tabs[activeTabId]?.ws) return;
    const ws = tabs[activeTabId].ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    //if (ws.readyState !== WebSocket.OPEN) return;
    setTabs((prev) => ({
      ...prev,
      [activeTabId]: {
        ...prev[activeTabId],
        isLoading: true,
        frameCount: 0,
      },
    }));
    const eventData = JSON.stringify({
      type: "navigation",
      pageId: activeTabId,
      event: action === "url" ? { url } : { action },
    });

    console.warn("Navigation Event:", {
      eventString: eventData,
      currentUrl: tabs[activeTabId].url,
      pageTitle: tabs[activeTabId].title,
      currentBase64Data: tabs[activeTabId].lastImageData,
      action,
      targetUrl: url,
    });

    ws.send(eventData);
    if (action === "url" && url) {
      window.parent.postMessage(
        {
          type: "navigation",
          url,
        },
        "*",
      );
    }
  };

  const isSecure = (url: string) =>
    url &&
    (url.toLowerCase().startsWith("https://") ||
      url.toLowerCase().startsWith("https:"));

  // UI
  return (
    <div className="container">
      <div className="browser-chrome">
        <div className="tab-bar" id="tab-bar">
          <div
            className={`connection-status ${connectionStatus}`}
            id="connection-status"
          >
            <div className={`status-indicator ${connectionStatus}`}></div>
            <span>
              {connectionStatus === "online"
                ? "Session Online"
                : connectionStatus === "offline"
                ? "Session Offline"
                : "Session Connecting..."}
            </span>
          </div>
          {tabOrder.map((id) => {
            const tab = tabs[id];
            return (
              <div
                key={id}
                className={`tab${activeTabId === id ? " active" : ""}${
                  tab.isLoading ? " loading" : ""
                }`}
                onClick={() => setActiveTabId(id)}
              >
                <img
                  className="tab-favicon"
                  src={tab.favicon || ""}
                  style={{ display: tab.favicon ? "block" : "none" }}
                  alt=""
                />
                <div className="tab-favicon-spinner"></div>
                <div className="tab-title">{tab.title || "New Tab"}</div>
                <div
                  className="tab-close"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleTabClosed(id);
                  }}
                >
                  &times;
                </div>
              </div>
            );
          })}
        </div>
        <div className="address-bar">
          <div className="nav-buttons">
            <button
              className="nav-button"
              onClick={() => handleNavigation("back")}
              disabled={!activeTabId}
            >
              <svg className="icon" viewBox="0 0 24 24">
                <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
              </svg>
            </button>
            <button
              className="nav-button"
              onClick={() => handleNavigation("forward")}
              disabled={!activeTabId}
            >
              <svg className="icon" viewBox="0 0 24 24">
                <path d="M12 4l-1.41 1.41L16.17 11H4v2h12.17l-5.58 5.59L12 20l8-8-8-8z" />
              </svg>
            </button>
            <button
              className="nav-button"
              onClick={() => handleNavigation("refresh")}
              disabled={!activeTabId}
            >
              <svg className="icon" viewBox="0 0 24 24">
                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
              </svg>
            </button>
          </div>
          <form className="url-bar" onSubmit={handleUrlSubmit}>
            <div
              className={`url-security-icon${
                isSecure(tabs[activeTabId || ""]?.url || "") ? " secure" : ""
              }`}
              id="url-security-icon"
            >
              <svg
                viewBox="0 0 24 24"
                id="lock-icon"
                style={{
                  display: isSecure(tabs[activeTabId || ""]?.url || "")
                    ? "block"
                    : "none",
                }}
              >
                <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z" />
              </svg>
              <svg
                viewBox="0 0 24 24"
                id="unlock-icon"
                style={{
                  display: isSecure(tabs[activeTabId || ""]?.url || "")
                    ? "none"
                    : "block",
                }}
              >
                <path d="M12 17c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm6-9h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h1.9c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10z" />
              </svg>
            </div>
            <input
              type="text"
              id="url-text"
              className="url-input"
              ref={urlTextRef}
              value={tabs[activeTabId || ""]?.url || ""}
              onChange={(e) => {
                if (!activeTabId || activeKey !== "3") return;
                setTabs((prev) => ({
                  ...prev,
                  [activeTabId]: {
                    ...prev[activeTabId],
                    url: e.target.value,
                  },
                }));
              }}
              onFocus={() => setIsUrlBarFocused(true)}
              onBlur={() => setIsUrlBarFocused(false)}
              disabled={!activeTabId}
            />
          </form>
        </div>
      </div>
      <div className="content">
        {tabOrder.map((id) => {
          const tab = tabs[id];
          return (
            <div
              key={id}
              ref={tab.containerRef}
              className={`canvas-container${
                activeTabId === id ? " active" : ""
              }${tab.isLoading ? " loading" : ""}${tab.error ? " error" : ""}`}
              style={{
                display: activeTabId === id ? "flex" : "none",
                width: "100%",
                height: "100%",
                position: "relative",
              }}
            >
              <canvas
                ref={tab.canvasRef}
                className="canvas"
                width={defaultWidth}
                height={defaultHeight}
                style={{ height: "100%", width: "auto" }}
                tabIndex={0}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Browser;
