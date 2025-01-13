import contextlib

from bot import LOGGER
from bot.helper.ext_utils.status_utils import (
    MirrorStatus,
    get_readable_file_size,
    get_readable_time,
)


class FFmpegStatus:
    def __init__(self, listener, obj, gid, status=""):
        self.listener = listener
        self._obj = obj
        self._gid = gid
        self._cstatus = status

    def speed(self):
        return f"{get_readable_file_size(self._obj.speed_raw)}/s"

    def processed_bytes(self):
        return get_readable_file_size(self._obj.processed_bytes)

    async def progress(self):
        return f"{round(self._obj.progress_raw, 2)}%"

    def gid(self):
        return self._gid

    def name(self):
        return self.listener.name

    def size(self):
        return get_readable_file_size(self.listener.size)

    def eta(self):
        return get_readable_time(self._obj.eta_raw) if self._obj.eta_raw else "-"

    def status(self):
        if self._cstatus == "Convert":
            return MirrorStatus.STATUS_CONVERT
        if self._cstatus == "Split":
            return MirrorStatus.STATUS_SPLIT
        if self._cstatus == "Sample Video":
            return MirrorStatus.STATUS_SAMVID
        if self._cstatus == "Metadata":
            return MirrorStatus.STATUS_METADATA
        if self._cstatus == "Watermark":
            return MirrorStatus.STATUS_WATERMARK
        return MirrorStatus.STATUS_FFMPEG

    def task(self):
        return self

    async def cancel_task(self):
        LOGGER.info(f"Cancelling {self._cstatus}: {self.listener.name}")
        self.listener.is_cancelled = True
        if (
            self.listener.subproc is not None
            and self.listener.subproc.returncode is None
        ):
            with contextlib.suppress(Exception):
                self.listener.subproc.kill()
        await self.listener.on_upload_error(f"{self._cstatus} stopped by user!")
