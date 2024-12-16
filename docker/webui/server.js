const express = require('express');
const WebSocket = require('ws');
const app = express();
const port = 3000;

// Track UE WebSocket clients and their log buffers
const ueWsClients = {};
const logBuffers = {};  // Buffer to store logs for each UE client
const localhostPortRange = { start: 8765, end: 8865 };

// Serve static files (HTML, CSS, JS)
app.use(express.static('public'));

// WebSocket server to broadcast UE logs to frontend clients
const server = app.listen(port, () => {
    console.log(`Express server running on http://localhost:${port}`);
});

const add_to_buffer = (ueKey, decodedMessage) => {
  if(!Object.keys(logBuffers[ueKey]).includes(decodedMessage.type)){
    logBuffers[ueKey][decodedMessage.type] = []
  }
  if(logBuffers[ueKey][decodedMessage.type].length >= 50){
    logBuffers[ueKey][decodedMessage.type].shift()
  }
  logBuffers[ueKey][decodedMessage.type].push(decodedMessage);
}

const wss = new WebSocket.Server({ server });
wss.on('connection', (ws) => {
    console.log("Client connection received");

    // Send buffered logs to the client upon connection
    Object.keys(logBuffers).forEach(ueKey => {
        Object.keys(logBuffers[ueKey]).forEach(logType => {
            logBuffers[ueKey][logType].forEach(log => {
                ws.send(JSON.stringify({ ueId: ueKey, text: log.text, type: logType }));
            });
        });
    });


    // Set up live streaming of new logs for the client
    Object.keys(ueWsClients).forEach(ueKey => {
        ueWsClients[ueKey].on('message', (message) => {
            const strMessage = Buffer.isBuffer(message) ? message.toString('utf-8') : message;
            const decodedMessage = JSON.parse(strMessage);
            ws.send(JSON.stringify({ ueId: ueKey, text: decodedMessage.text, type: decodedMessage.type}));
            add_to_buffer(ueKey, decodedMessage);
        });
    });

    ws.on('close', () => {
        console.log("Client disconnected");
    });
});

// Scan the localhost port range for available WebSocket servers
async function scanLocalhostPorts() {
    for (let port = localhostPortRange.start; port <= localhostPortRange.end; port++) {
        const url = `ws://localhost:${port}`;
        const ueKey = `UE-${port}`;

        try {
            const ueWs = new WebSocket(url);

            ueWs.on('open', () => {
                console.log(`Connected to WebSocket at ${url}`);
                ueWsClients[ueKey] = ueWs; // Store connection
                logBuffers[ueKey] = logBuffers[ueKey] || [];  // Initialize buffer for UE logs
            });

            ueWs.on('message', (message) => {
                const decodedMessage = Buffer.isBuffer(message) ? message.toString('utf-8') : message;
                let parsedMessage;

                try {
                    parsedMessage = JSON.parse(decodedMessage); // Attempt to parse JSON
                } catch (error) {
                    console.log(`Failed to parse message: ${error}`);  // Log parsing errors
                    return; // Skip further processing if JSON is invalid
                }
                console.log(parsedMessage)

                add_to_buffer(ueKey, parsedMessage);
            });

            ueWs.on('close', () => {
                console.log(`${ueKey} WebSocket closed`);
                delete ueWsClients[ueKey];
            });

            ueWs.on('error', (error) => {
                console.log(`Failed to connect to WebSocket at ${url}: ${error.message}`);
            });
        } catch (error) {
            console.log(`Error connecting to ${url}: ${error.message}`);
        }
    }
}

scanLocalhostPorts();


