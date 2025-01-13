import json
import os
from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE

from bot import LOGGER


async def get_streams(file):
    cmd = [
        "ffprobe",
        "-hide_banner",
        "-loglevel",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        file,
    ]
    process = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        LOGGER.error(f"Error getting stream info: {stderr.decode().strip()}")
        return None

    try:
        return json.loads(stdout)["streams"]
    except KeyError:
        LOGGER.error(
            f"No streams found in the ffprobe output: {stdout.decode().strip()}",
        )
        return None


# Lots of work need
async def get_watermark_cmd(file, key):
    temp_file = f"{file}.temp.mkv"
    font_path = "rizz.otf"

    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-i",
        file,
        "-vf",
        f"drawtext=text='{key}':fontfile={font_path}:fontsize=20:fontcolor=white:x=10:y=10",
        temp_file,
    ]

    return cmd, temp_file


async def get_metadata_cmd(file_path, key):
    """Processes a single file to update metadata."""
    temp_file = f"{file_path}.temp.mkv"
    streams = await get_streams(file_path)
    if not streams:
        return None, None

    languages = {
        stream["index"]: stream["tags"]["language"]
        for stream in streams
        if "tags" in stream and "language" in stream["tags"]
    }

    cmd = [
        "xtra",
        "-hide_banner",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-i",
        file_path,
        "-map_metadata",
        "-1",
        "-c",
        "copy",
        "-metadata:s:v:0",
        f"title={key}",
        "-metadata",
        f"title={key}",
    ]

    audio_index = 0
    subtitle_index = 0
    first_video = False

    for stream in streams:
        stream_index = stream["index"]
        stream_type = stream["codec_type"]

        if stream_type == "video":
            if not first_video:
                cmd.extend(["-map", f"0:{stream_index}"])
                first_video = True
            cmd.extend([f"-metadata:s:v:{stream_index}", f"title={key}"])
            if stream_index in languages:
                cmd.extend(
                    [
                        f"-metadata:s:v:{stream_index}",
                        f"language={languages[stream_index]}",
                    ],
                )
        elif stream_type == "audio":
            cmd.extend(
                [
                    "-map",
                    f"0:{stream_index}",
                    f"-metadata:s:a:{audio_index}",
                    f"title={key}",
                ],
            )
            if stream_index in languages:
                cmd.extend(
                    [
                        f"-metadata:s:a:{audio_index}",
                        f"language={languages[stream_index]}",
                    ],
                )
            audio_index += 1
        elif stream_type == "subtitle":
            codec_name = stream.get("codec_name", "unknown")
            if codec_name in ["webvtt", "unknown"]:
                LOGGER.warning(
                    f"Skipping unsupported subtitle metadata modification: {codec_name} for stream {stream_index}",
                )
            else:
                cmd.extend(
                    [
                        "-map",
                        f"0:{stream_index}",
                        f"-metadata:s:s:{subtitle_index}",
                        f"title={key}",
                    ],
                )
                if stream_index in languages:
                    cmd.extend(
                        [
                            f"-metadata:s:s:{subtitle_index}",
                            f"language={languages[stream_index]}",
                        ],
                    )
                subtitle_index += 1
        else:
            cmd.extend(["-map", f"0:{stream_index}"])

    cmd.append(temp_file)
    return cmd, temp_file


async def add_attachment(file, attachment_path):
    LOGGER.info(f"Adding photo attachment to file: {file}")

    temp_file = f"{file}.temp.mkv"

    attachment_ext = attachment_path.split(".")[-1].lower()
    mime_type = "application/octet-stream"
    if attachment_ext in ["jpg", "jpeg"]:
        mime_type = "image/jpeg"
    elif attachment_ext == "png":
        mime_type = "image/png"

    cmd = [
        "xtra",
        "-y",
        "-i",
        file,
        "-attach",
        attachment_path,
        "-metadata:s:t",
        f"mimetype={mime_type}",
        "-c",
        "copy",
        "-map",
        "0",
        temp_file,
    ]

    process = await create_subprocess_exec(*cmd, stderr=PIPE, stdout=PIPE)
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        err = stderr.decode().strip()
        LOGGER.error(err)
        LOGGER.error(f"Error adding photo attachment to file: {file}")
        return

    os.replace(temp_file, file)
    LOGGER.info(f"Photo attachment added successfully to file: {file}")
    return
