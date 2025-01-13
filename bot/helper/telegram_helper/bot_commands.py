# ruff: noqa: RUF012
from bot.core.config_manager import Config

i = Config.CMD_SUFFIX


class BotCommands:
    StartCommand = f"start"
    MirrorCommand = [f"mirror{i}", f"m{i}"]
    YtdlCommand = [f"ytdl{i}", f"y{i}"]
    LeechCommand = [f"leech{i}", f"l{i}"]
    YtdlLeechCommand = [f"ytdlleech{i}", f"yl{i}"]
    CloneCommand = f"clone{i}"
    MediaInfoCommand = f"mediainfo{i}"
    CountCommand = f"count{i}"
    DeleteCommand = f"del{i}"
    CancelAllCommand = f"cancelall{i}"
    ForceStartCommand = [f"forcestart{i}", f"fs{i}"]
    ListCommand = f"list{i}"
    SearchCommand = f"search{i}"
    StatusCommand = [f"status{i}", "sall"]
    UsersCommand = f"users{i}"
    AuthorizeCommand = f"authorize{i}"
    UnAuthorizeCommand = f"unauthorize{i}"
    AddSudoCommand = f"addsudo{i}"
    RmSudoCommand = f"rmsudo{i}"
    PingCommand = [f"ping{i}", "p"]
    RestartCommand = f"restart{i}"
    RestartSessionsCommand = f"restartses{i}"
    StatsCommand = f"stats{i}"
    HelpCommand = f"help{i}"
    LogCommand = f"log{i}"
    ShellCommand = f"shell{i}"
    AExecCommand = f"aexec{i}"
    ExecCommand = f"exec{i}"
    ClearLocalsCommand = f"clearlocals{i}"
    BotSetCommand = f"bsetting{i}"
    UserSetCommand = f"usetting{i}"
    SpeedTest = f"speedtest{i}"
    BroadcastCommand = [f"broadcast{i}", "broadcastall"]
    SelectCommand = f"btsel{i}"
    RssCommand = f"rss{i}"
