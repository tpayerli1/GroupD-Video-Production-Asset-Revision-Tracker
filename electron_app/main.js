const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { execFile } = require("child_process");
const ffmpegPath = require("ffmpeg-static");
const ffprobe = require("ffprobe-static");

ipcMain.handle("uploader:get-binary-paths", () => ({
  ffmpegPath: ffmpegPath || null,
  ffprobePath: ffprobe?.path || null,
}));

function runFfprobe(filePath) {
  return new Promise((resolve, reject) => {
    if (!ffprobe?.path) {
      reject(new Error("ffprobe binary not available"));
      return;
    }

    execFile(
      ffprobe.path,
      ["-v", "error", "-print_format", "json", "-show_format", "-show_streams", filePath],
      { windowsHide: true },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(stderr || error.message || "ffprobe failed"));
          return;
        }

        try {
          resolve(JSON.parse(stdout || "{}"));
        } catch (parseError) {
          reject(new Error(`Invalid ffprobe JSON: ${parseError.message}`));
        }
      }
    );
  });
}

function parseFraction(value) {
  if (!value || value === "0/0" || value === "N/A") return null;
  if (String(value).includes("/")) {
    const [num, den] = String(value).split("/").map(Number);
    if (!num || !den) return null;
    return Number((num / den).toFixed(3));
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Number(numeric.toFixed(3)) : null;
}

function parseIntValue(value) {
  if (value === null || value === undefined || value === "" || value === "N/A") return null;
  const numeric = Number.parseInt(value, 10);
  return Number.isFinite(numeric) ? numeric : null;
}

function parseFloatValue(value) {
  if (value === null || value === undefined || value === "" || value === "N/A") return null;
  const numeric = Number.parseFloat(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function detectFileType(filePath, streams) {
  const extension = path.extname(filePath).toLowerCase();
  const imageExtensions = new Set([".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"]);
  if (imageExtensions.has(extension)) return "image";

  const streamTypes = (streams || []).map((stream) => stream.codec_type);
  if (streamTypes.includes("video")) return "video";
  if (streamTypes.includes("audio")) return "audio";
  return extension.replace(".", "") || "unknown";
}

function detectHdr(stream) {
  const transfer = String(stream?.color_transfer || "").toLowerCase();
  const primaries = String(stream?.color_primaries || "").toLowerCase();

  if (transfer === "smpte2084" || transfer === "arib-std-b67") return true;
  if (primaries.includes("bt2020")) return true;
  if (transfer || primaries) return false;
  return null;
}

function extractMetadata(filePath, payload) {
  const streams = payload?.streams || [];
  const format = payload?.format || {};
  const videoStream = streams.find((stream) => stream.codec_type === "video");
  const audioStream = streams.find((stream) => stream.codec_type === "audio");
  const primaryStream = videoStream || audioStream || streams[0] || {};

  return {
    file_type: detectFileType(filePath, streams),
    file_size: parseIntValue(format.size),
    imported_at: new Date().toISOString(),
    has_color_grade: false,
    hdr: detectHdr(primaryStream),
    frame_rate: parseFraction(primaryStream.avg_frame_rate || primaryStream.r_frame_rate),
    codec: primaryStream.codec_name || format.format_name || "",
    duration: parseFloatValue(primaryStream.duration || format.duration),
    width: parseIntValue(primaryStream.width),
    height: parseIntValue(primaryStream.height),
    aspect_ratio:
      primaryStream.display_aspect_ratio && primaryStream.display_aspect_ratio !== "N/A"
        ? primaryStream.display_aspect_ratio
        : "",
    color_space: primaryStream.color_space || "",
    bit_rate: parseIntValue(primaryStream.bit_rate || format.bit_rate),
  };
}

ipcMain.handle("uploader:probe-media-file", async (_event, filePath) => {
  const probePayload = await runFfprobe(filePath);
  return extractMetadata(filePath, probePayload);
});

function createWindow() {
  const win = new BrowserWindow({
    width: 1000,
    height: 1200,
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
