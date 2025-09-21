const fs = require("fs");
const yaml = require("js-yaml");

// read yml
const config = yaml.load(fs.readFileSync("../config.yml", "utf8"));

// get port
const backend_port = config.backend.port || 9000;
const backend_host = config.backend.host || "localhost";
const frontend_port = config.frontend.port || 3000;

// write .env
fs.writeFileSync(".env", `REACT_APP_API_URL=http://${backend_host}:${backend_port}\n`);
fs.writeFileSync(".env", `PORT=${frontend_port}\n`, { flag: "a" });
