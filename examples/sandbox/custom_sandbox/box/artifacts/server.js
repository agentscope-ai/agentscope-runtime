const express = require("express");
const http = require("http");
const socketIo = require("socket.io");
const pty = require("node-pty");
const fs = require("fs");
const path = require("path");

const app = express();
const server = http.createServer(app);
const workspaceDir = process.env.WORKSPACE_DIR || __dirname;
const SECRET_TOKEN = process.env.SECRET_TOKEN;


const io = socketIo(server, {
  cors: {
    origin: "*", methods: ["GET", "POST"]
  }
});

// 创建单一的 namespace: v1
const artifactsNsp = io.of("/v1");

// Middleware for token authentication
artifactsNsp.use((socket, next) => {
  const token = socket.handshake.auth.token; // Assuming the token is sent as part of the auth object
  if (token === SECRET_TOKEN) {
    return next();
  }
  const err = new Error("Authentication error");
  err.data = { content: "Authentication failed due to invalid token" }; // Optional data
  next(err);
});


// Get filtered environment variables
function getFilteredEnv() {
  const safeEnv = {};
  const sensitiveKeys = [
    "SECRET_TOKEN", "PASSWORD", "SECRET", "KEY", "TOKEN", "PASS",
    "AWS_", "AZURE_", "GCP_", "GOOGLE_", "DATABASE_", "DB_",
    "REDIS_", "MONGO_", "API_KEY", "PRIVATE_KEY", "CERT", "SSL_",
    "OAUTH", "JWT", "COOKIE", "SESSION", "AUTH"
  ];

  for (const [key, value] of Object.entries(process.env)) {
    const isSensitive = sensitiveKeys.some(sensitive =>
      key.toUpperCase().includes(sensitive)
    );

    if (!isSensitive) {
      safeEnv[key] = value;
    }
  }

  return safeEnv;
}

function isDangerousCommand(input) {
  const trimmedInput = input.trim().toLowerCase();

  const bannedCommands = ["sudo", "su","passwd", "chroot", "usermod", "userdel","useradd",
    "shutdown", "reboot", "halt", "poweroff", "init",
    "mkfs", "fdisk", "parted","gparted", "lsblk",
    "mount", "umount", "dd", "killall", "pkill", "kill",
    "iptables","ufw", "firewall-cmd",
    "systemctl", "service", "systemd",
    "crontab", "at", "batch", "ps", "top", "htop", "pgrep"
  ];

  // 简单粗暴：检查输入中是否包含任何禁止的命令
  for (const bannedCmd of bannedCommands) {
    if (trimmedInput.includes(bannedCmd)) {
      return true;
    }
  }

  //检查危险的命令分隔符组合
  const dangerousPatterns = [
    /&&.*(?:sudo|su|rm|chmod|chown|shutdown|reboot)/i,
    /\|\|.*(?:sudo|su|rm|chmod|chown|shutdown|reboot)/i,
    /;.*(?:sudo|su|rm|chmod|chown|shutdown|reboot)/i,
    /\|.*(?:sudo|su|rm|chmod|chown|shutdown|reboot)/i,
    /(?:sudo|su|rm|chmod|chown|shutdown|reboot).*&&/i,
    /(?:sudo|su|rm|chmod|chown|shutdown|reboot).*\|\|/i,/(?:sudo|su|rm|chmod|chown|shutdown|reboot).*;/i,
    /(?:sudo|su|rm|chmod|chown|shutdown|reboot).*\|/i,
    /\$\([^)]*(?:sudo|su|rm|chmod|chown|shutdown|reboot)/i,/`[^`]*(?:sudo|su|rm|chmod|chown|shutdown|reboot)/i,/^rm\s+(-[rf]*|--recursive|--force).*(\/|\~|\*)/i,
    /^chmod\s+(777|755|666).*(\/)/i,
    /^chown\s+.*(\/)/,
    />\s*\/dev\/sd[a-z]/i,
    /curl.*\|\s*(sh|bash|zsh)/i,
    /wget.*\|\s*(sh|bash|zsh)/i,
    />\s*\/etc\//i,
    />\s*\/usr\/bin/i,
    />\s*\/bin/i,
    /fork.*bomb/i,
    /:.*\{\s*:\s*\|\s*:/i,
  ];

  return dangerousPatterns.some(pattern => pattern.test(trimmedInput));
}

function isPathWithinWorkspace(filePath) {
  // Resolve absolute paths
  const fullPath = path.resolve(workspaceDir, filePath);
  const resolvedWorkspaceDir = path.resolve(workspaceDir);

  // Check if fullPath is within resolvedWorkspaceDir
  return fullPath.startsWith(resolvedWorkspaceDir);
}

function getFileTree(dir) {
  const resolvedDir = path.resolve(dir);

  if (!isPathWithinWorkspace(resolvedDir)) {
    throw new Error("Access to the directory is not allowed.");
  }

  const result = [];
  const items = fs.readdirSync(dir);

  items.forEach(item => {
    // Skip hidden files and directories
    if (item.startsWith(".")) {
      return;
    }

    const fullPath = path.join(dir, item);
    const stats = fs.statSync(fullPath);
    const relativePath = path.relative(workspaceDir, fullPath);

    if (stats.isDirectory()) {
      result.push({
        name: item,
        type: "directory",
        path: relativePath,
        children: getFileTree(fullPath)
      });
    } else {
      result.push({
        name: item,
        type: "file",
        path: relativePath
      });
    }
  });

  return result;
}

artifactsNsp.on("connection", (socket) => {
  console.log("A user connected to artifacts namespace");
  const shell = process.platform === "win32" ? "powershell.exe" : "bash";
  const ptyProcess = pty.spawn(shell, [], {
    name: "xterm-color",
    cols: 80,
    rows: 30,
    cwd: workspaceDir,
    env: getFilteredEnv()
  });

  ptyProcess.on("data", (data) => {
    socket.emit("output", data);
  });

  let currentInput = "";
  socket.on("input", (input) => {
    // 累积输入
    currentInput += input;
    console.log(`Received input: ${currentInput}`);

    // 检查是否包含换行符，表示输入结束
    if (currentInput.includes("\r") || currentInput.includes("\n")) {
      // 获取当前输入的完整命令进行检查
      const command = currentInput.replace(/[\r\n]/g, "").trim();
      console.log(`Received complete command: ${command}`);

      // 检查危险命令
      if (isDangerousCommand(command)) {
        socket.emit("output", "\r\n\u001b[31mError: This command is not allowed for security reasons.\u001b[0m\r\n");
        currentInput = ""; // 重置输入
        ptyProcess.write("\u0015"); // Ctrl+U 清空行
        ptyProcess.write("\u0003"); // Ctrl+C 中断
        return;
      }

      // 重置输入
      currentInput = "";
    }

    // 将输入传递给PTY进程
    ptyProcess.write(input);
  });

  socket.on("disconnect", () => {
    console.log("A user disconnected from artifacts namespace");
    ptyProcess.kill();
  });

  socket.on("requestFileList", () => {
    try {
      const fileTree = getFileTree(workspaceDir);
      socket.emit("fileTree", fileTree);
    } catch (err) {
      socket.emit("output", `Error listing files: ${err.message}`);
    }
  });

  socket.on("loadFile", (filePath) => {
    if (!isPathWithinWorkspace(filePath)) {
      socket.emit("output", "Error: Access to the file is not allowed.");
      return;
    }

    const fullPath = path.join(workspaceDir, filePath);
    fs.readFile(fullPath, "utf8", (err, data) => {
      if (err) {
        socket.emit("output", `Error loading file: ${err.message}`);
        return;
      }
      socket.emit("fileContent", {content: data, path: filePath});
    });
  });

  socket.on("saveFile", ({filename, content}) => {
    if (!isPathWithinWorkspace(filename)) {
      socket.emit("fileSaved", {
        success: false,
        error: "Error: Access to the file is not allowed."
      });
      return;
    }

    const filePath = path.join(workspaceDir, filename);
    fs.writeFile(filePath, content, "utf8", (err) => {
      if (err) {
        socket.emit("fileSaved", {
          success: false,
          error: err.message
        });
        return;
      }
      socket.emit("fileSaved", {
        success: true,
        path: filename
      });
    });
  });

  ptyProcess.write("clear\n");
});

const PORT = 4500;
server.listen(PORT, "0.0.0.0", () => {
  console.log(`Server running at http://0.0.0.0:${PORT}/`);
  console.log(`Server also accessible at http://localhost:${PORT}/`);
});