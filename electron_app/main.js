const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const ffmpegPath = require("ffmpeg-static");
const ffprobe = require("ffprobe-static");

ipcMain.handle("uploader:get-binary-paths", () => ({
  ffmpegPath: ffmpegPath || null,
  ffprobePath: ffprobe?.path || null,
}));

function createWindow() {
  const win = new BrowserWindow({
    width: 900,
    height: 900,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  win.loadFile("index.html");
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  app.quit();
});
