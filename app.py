from flask import Flask, request, jsonify
import yt_dlp
import os

app = Flask(__name__)

SECRET_FILE_PATH = "/etc/secrets/cookies.txt"
FALLBACK_COOKIES_PATH = "/tmp/cookies.txt"

# Preferred: Render "Secret Files" — these preserve multi-line content correctly,
# unlike the plain environment variable UI, which can mangle/flatten newlines
# when pasted. Falls back to the YTDLP_COOKIES env var for other hosts/local dev.
#
# Note: yt-dlp writes back to the cookiejar file (to persist any session
# cookies YouTube rotates mid-request), so it needs a *writable* path.
# Render's Secret Files are mounted read-only, so we copy the contents into
# /tmp first rather than pointing yt-dlp at /etc/secrets directly.
if os.path.exists(SECRET_FILE_PATH):
    with open(SECRET_FILE_PATH, "r", encoding="utf-8") as src:
        _cookie_contents = src.read()
    with open(FALLBACK_COOKIES_PATH, "w", encoding="utf-8") as dst:
        dst.write(_cookie_contents)
    _cookies_file = FALLBACK_COOKIES_PATH
else:
    _raw_cookies = os.environ.get("YTDLP_COOKIES")
    if _raw_cookies:
        with open(FALLBACK_COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(_raw_cookies)
        _cookies_file = FALLBACK_COOKIES_PATH
    else:
        _cookies_file = None

YDL_OPTS = {
    # Only pick formats that already have both video and audio in one file
    # (a "progressive" stream). Modern YouTube mostly serves separate
    # video-only/audio-only adaptive streams above ~360-720p, which would
    # need a local ffmpeg merge — this trades max resolution for always
    # getting back one ready-to-use direct URL.
    "format": "best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/best",
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "skip_download": True,
    # If YouTube's "web" client breaks (as with the ongoing SABR rollout),
    # fall back to other clients rather than failing outright.
    "extractor_args": {
        "youtube": {
            "player_client": ["android", "ios", "web"],
        }
    },
}
if _cookies_file:
    YDL_OPTS["cookiefile"] = _cookies_file


@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "ytdlp-resolver",
        "cookies_loaded": _cookies_file is not None,
    })


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
        error_message = str(e)

        # If it failed specifically on format selection, re-query with no
        # format restriction so we can see what YouTube actually offered —
        # this tells us whether a progressive (single-file) stream exists
        # at all for this video, without needing another deploy cycle.
        if "Requested format is not available" in error_message:
            try:
                diag_opts = dict(YDL_OPTS)
                diag_opts.pop("format", None)
                with yt_dlp.YoutubeDL(diag_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    formats = [
                        {
                            "format_id": f.get("format_id"),
                            "ext": f.get("ext"),
                            "resolution": f.get("resolution"),
                            "vcodec": f.get("vcodec"),
                            "acodec": f.get("acodec"),
                            "has_url": bool(f.get("url")),
                        }
                        for f in info.get("formats", [])
                    ]
                    return jsonify({
                        "status": "error",
                        "message": error_message,
                        "available_formats": formats,
                    }), 422
            except Exception:
                pass  # fall through to the plain error below

        return jsonify({"status": "error", "message": error_message}), 422
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
