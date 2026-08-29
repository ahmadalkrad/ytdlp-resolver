from flask import Flask, request, jsonify
import yt_dlp
import os

app = Flask(__name__)

YDL_OPTS = {
    "format": "best[ext=mp4]/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "skip_download": True,
}


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ytdlp-resolver"})


@app.route("/resolve", methods=["POST"])
def resolve():
    data = request.get_json(silent=True) or {}
    url = data.get("url")

    if not url:
        return jsonify({"status": "error", "message": "url is required"}), 400

    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)

            direct_url = info.get("url")
            if not direct_url and info.get("requested_formats"):
                # some extractions split video/audio; fall back to the first format's url
                direct_url = info["requested_formats"][0].get("url")

            if not direct_url:
                return jsonify({
                    "status": "error",
                    "message": "no direct url found in extracted info"
                }), 502

            return jsonify({
                "status": "ok",
                "title": info.get("title"),
                "url": direct_url,
                "ext": info.get("ext", "mp4"),
                "duration": info.get("duration"),
            })
    except yt_dlp.utils.DownloadError as e:
        return jsonify({"status": "error", "message": str(e)}), 422
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
