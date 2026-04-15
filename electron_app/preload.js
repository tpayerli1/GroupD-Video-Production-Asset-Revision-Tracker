const { contextBridge } = require("electron");
const ffmpegPath = require("ffmpeg-static");
const ffprobe = require("ffprobe-static");

contextBridge.exposeInMainWorld("uploader", {
  post: async (url, payload) => {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });

    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { raw: text };
    }

    if (!res.ok) {
      const msg = data?.detail || data?.error || `HTTP ${res.status}`;
      throw new Error(msg);
    }

    return data;
  },
  getBinaryPaths: () => ({
    ffmpegPath: ffmpegPath || null,
    ffprobePath: ffprobe.path || null,
  }),
});
