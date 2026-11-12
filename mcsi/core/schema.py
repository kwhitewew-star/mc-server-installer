"""Settings definitions. level: 'b' = shown in standard mode too, 'a' = detailed mode only."""

from __future__ import annotations
from ..i18n import _

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class S:
    key: str
    label: str
    type: str                     # bool | int | str | choice | secret
    default: Any
    group: str
    desc: str = ""
    level: str = "a"
    min: int = 0
    max: int = 2_147_483_647
    choices: list = field(default_factory=list)   # [(value, label)]
    rule_old: Optional[str] = None  # game rule (name up to 1.21.10)
    rule_new: Optional[str] = None  # game rule (name from 1.21.11)
    invert_old: bool = False        # old name has inverted meaning, like disableRaids
    note: str = ""


DIFF = [("peaceful", _("Peaceful")), ("easy", _("Easy")), ("normal", _("Normal")), ("hard", _("Hard"))]
MODES = [("survival", _("Survival")), ("creative", _("Creative")), ("adventure", _("Adventure")), ("spectator", _("Spectator"))]
LEVEL_TYPES = [("minecraft:normal", _("Basic")), ("minecraft:flat", _("Flat")), ("minecraft:large_biomes", _("Large biomes")),
               ("minecraft:amplified", _("Amplified")), ("minecraft:single_biome_surface", _("Single biome"))]
COMPRESS = [("deflate", _("deflate (default)")), ("lz4", _("lz4 (fast, larger files)")), ("none", _("No compression"))]
MOVED = _("On 1.21.9+ this is applied as the game rule of the same name (needs first run).")

# ---------------------------------------------------------------- server.properties
PROPS: list[S] = [
    # Basics
    S("motd", _("Server description (MOTD)"), "str", "A Minecraft Server", _("Basic"),
      _("Text shown in the server list. Color codes like §a work"), "b"),
    S("max-players", _("Max players"), "int", 20, _("Basic"), _("Maximum players online at once"), "b", 1, 10000),
    S("server-port", _("Server port"), "int", 25565, _("Basic"), _("Connection port (1024–65535). Use this number for port forwarding too"), "b", 1024, 65535),
    S("server-ip", _("Bind IP"), "str", "", _("Basic"), _("Leave empty to accept connections on all networks")),
    S("level-name", _("World folder name"), "str", "world", _("Basic"), _("Folder where the world is saved"), "b"),
    S("bug-report-link", _("Bug report link"), "str", "", _("Basic"), _("Link shown on the connection error screen")),
    # Access / security
    S("online-mode", _("Online mode (premium only)"), "bool", True, _("Access & security"),
      _("Off allows cracked clients, but anyone can impersonate a name"), "b"),
    S("white-list", _("Whitelist"), "bool", False, _("Access & security"), _("Only allowed players can join"), "b"),
    S("enforce-whitelist", _("Enforce whitelist"), "bool", False, _("Access & security"),
      _("Kick players removed from the list immediately")),
    S("enforce-secure-profile", _("Enforce secure profile"), "bool", True, _("Access & security"), _("Only signed chat allowed")),
    S("prevent-proxy-connections", _("Prevent proxy connections"), "bool", False, _("Access & security"), _("Block suspected VPN/proxy connections")),
    S("log-ips", _("Log IPs"), "bool", True, _("Access & security"), _("Log player IPs")),
    S("op-permission-level", _("Default op permission level"), "int", 4, _("Access & security"), _("1-4. 4 = all permissions"), "a", 0, 4),
    S("function-permission-level", _("Function permission level"), "int", 2, _("Access & security"), _("Permission level for datapack functions"), "a", 1, 4),
    S("rate-limit", _("Rate limit"), "int", 0, _("Access & security"), _("Packets per second limit (0 = off)")),
    S("accepts-transfers", _("Accept transfers"), "bool", False, _("Access & security"), _("Allow players sent with /transfer")),
    S("hide-online-players", _("Hide online players"), "bool", False, _("Access & security"), _("Hide player names in the server list")),
    S("enable-status", _("Show in server list"), "bool", True, _("Access & security"), _("Off makes the server look offline in the list")),
    S("enable-code-of-conduct", _("Code of conduct"), "bool", False, _("Access & security"),
      _("Shows the rules from the codeofconduct folder on join (1.21.9+)")),
    S("player-idle-timeout", _("AFK kick (minutes)"), "int", 0, _("Access & security"), _("0 = never kick"), "b", 0, 100000),
    # Gameplay
    S("gamemode", _("Default game mode"), "choice", "survival", _("Gameplay"), "", "b", choices=MODES),
    S("force-gamemode", _("Force game mode"), "bool", False, _("Gameplay"), _("Reset to the default game mode on every join")),
    S("difficulty", _("Difficulty"), "choice", "easy", _("Gameplay"), "", "b", choices=DIFF),
    S("hardcore", _("Hardcore"), "bool", False, _("Gameplay"), _("Death puts you in spectator. Only applies when the world is created"), "b"),
    S("pvp", _("Allow PvP"), "bool", True, _("Gameplay"), _("Players can attack each other"), "b",
      rule_old="pvp", rule_new="pvp", note=MOVED),
    S("allow-flight", _("Allow flight (no kick)"), "bool", False, _("Gameplay"),
      _("Prevents the 'flying is not enabled' kick. Recommended for modded servers"), "b"),
    S("enable-command-block", _("Command blocks"), "bool", False, _("Gameplay"), "", "b",
      rule_old="commandBlocksEnabled", rule_new="command_blocks_work", note=MOVED),
    S("spawn-protection", _("Spawn protection radius"), "int", 16, _("Gameplay"), _("Radius around spawn that non-ops cannot change"), "b",
      0, 1000),
    S("max-world-size", _("Max world size"), "int", 29999984, _("Gameplay"), _("World border radius (blocks)"), "a", 1, 29999984),
    # World generation
    S("level-seed", _("World seed"), "str", "", _("World generation"), _("Leave empty for random"), "b"),
    S("level-type", _("World type"), "choice", "minecraft:normal", _("World generation"), "", "b", choices=LEVEL_TYPES),
    S("generate-structures", _("Generate structures"), "bool", True, _("World generation"), _("Villages, temples and more")),
    S("generator-settings", _("Generator settings (JSON)"), "str", "{}", _("World generation"), _("Details for flat/single biome worlds")),
    S("allow-nether", _("Allow the Nether"), "bool", True, _("World generation"), "", "b",
      rule_old="allowEnteringNetherUsingPortals", rule_new="allow_entering_nether_using_portals", note=MOVED),
    S("initial-enabled-packs", _("Initially enabled datapacks"), "str", "vanilla", _("World generation"), _("Separated by commas")),
    S("initial-disabled-packs", _("Initially disabled datapacks"), "str", "", _("World generation"), _("Separated by commas")),
    S("region-file-compression", _("Region file compression"), "choice", "deflate", _("World generation"), "", choices=COMPRESS),
    # Spawning (old-version properties)
    S("spawn-monsters", _("Spawn monsters"), "bool", True, _("Spawning"), "", "b",
      rule_old="spawnMonsters", rule_new="spawn_monsters", note=MOVED),
    S("spawn-animals", _("Spawn animals"), "bool", True, _("Spawning"), _("Only for older versions")),
    S("spawn-npcs", _("Spawn villagers"), "bool", True, _("Spawning"), _("Only for older versions")),
    # Performance
    S("view-distance", _("View distance (chunks)"), "int", 10, _("Performance"), _("Higher is farther but heavier"), "b", 3, 32),
    S("simulation-distance", _("Simulation distance"), "int", 10, _("Performance"), _("Distance where mobs and crops are updated"), "b", 3, 32),
    S("entity-broadcast-range-percentage", _("Entity broadcast range %"), "int", 100, _("Performance"), "", "a", 10, 1000),
    S("pause-when-empty-seconds", _("Pause when empty (s)"), "int", 60, _("Performance"),
      _("Pauses after this long with nobody online. 0 = keep running (for farms)"), "b", 0, 100000000),
    S("max-tick-time", _("Max tick time (ms)"), "int", 60000, _("Performance"), _("-1 disables the watchdog"), "a", -1, 2_147_483_647),
    S("network-compression-threshold", _("Network compression threshold"), "int", 256, _("Performance"), _("-1 = no compression"), "a", -1, 65535),
    S("max-chained-neighbor-updates", _("Max chained neighbor updates"), "int", 1000000, _("Performance"), "", "a", -1, 2_147_483_647),
    S("sync-chunk-writes", _("Synchronous chunk writes"), "bool", True, _("Performance"), _("Faster when off, but risk of corruption on power loss")),
    S("use-native-transport", _("Native networking (Linux)"), "bool", True, _("Performance")),
    S("enable-jmx-monitoring", _("JMX monitoring"), "bool", False, _("Performance")),
    # Resource pack
    S("resource-pack", _("Resource pack URL"), "str", "", _("Resource pack"), _("Direct download link")),
    S("resource-pack-sha1", _("Resource pack SHA-1"), "str", "", _("Resource pack")),
    S("resource-pack-id", _("Resource pack UUID"), "str", "", _("Resource pack")),
    S("resource-pack-prompt", _("Resource pack prompt"), "str", "", _("Resource pack")),
    S("require-resource-pack", _("Require resource pack"), "bool", False, _("Resource pack"), _("Players who decline cannot join")),
    # Remote management
    S("enable-rcon", _("Enable RCON"), "bool", False, _("Remote management"), _("Run commands from external tools")),
    S("rcon.port", _("RCON port"), "int", 25575, _("Remote management"), "", "a", 1024, 65535),
    S("rcon.password", _("RCON password"), "secret", "", _("Remote management")),
    S("broadcast-rcon-to-ops", _("Broadcast RCON commands to ops"), "bool", True, _("Remote management")),
    S("broadcast-console-to-ops", _("Broadcast console commands to ops"), "bool", True, _("Remote management")),
    S("enable-query", _("Query protocol"), "bool", False, _("Remote management"), _("Protocol for querying server info")),
    S("query.port", _("Query port"), "int", 25565, _("Remote management"), "", "a", 1024, 65535),
    S("management-server-enabled", _("Enable management API"), "bool", False, _("Remote management"), _("Server management protocol (1.21.9+)")),
    S("management-server-host", _("Management API host"), "str", "localhost", _("Remote management")),
    S("management-server-port", _("Management API port"), "int", 0, _("Remote management"), _("0 = automatic"), "a", 0, 65535),
    S("management-server-secret", _("Management API secret"), "secret", "", _("Remote management"),
      _("Leave empty to generate a 40-character key")),
    S("management-server-tls-enabled", _("Management API TLS"), "bool", True, _("Remote management")),
    S("management-server-tls-keystore", _("TLS keystore path"), "str", "", _("Remote management")),
    S("management-server-tls-keystore-password", _("TLS keystore password"), "secret", "", _("Remote management")),
    S("management-server-allowed-origins", _("Management API allowed origins"), "str", "", _("Remote management"), _("Separated by commas")),
    S("status-heartbeat-interval", _("Management API heartbeat (s)"), "int", 0, _("Remote management"), _("0 = off")),
    S("text-filtering-config", _("Text filtering config"), "str", "", _("Remote management")),
    S("text-filtering-version", _("Text filtering version"), "int", 0, _("Remote management"), "", "a", 0, 1),
]


def R(old, new, label, typ, default, group, desc="", level="a", mn=0, mx=2_147_483_647, invert=False):
    return S(f"rule:{new or old}", label, typ, default, group, desc, level, mn, mx,
             rule_old=old, rule_new=new, invert_old=invert)


# ---------------------------------------------------------------- Game rules
RULES: list[S] = [
    R("keepInventory", "keep_inventory", _("Keep inventory on death"), "bool", False, _("Player"), "", "b"),
    R("naturalRegeneration", "natural_health_regeneration", _("Natural health regeneration"), "bool", True, _("Player"), "", "b"),
    R("doImmediateRespawn", "immediate_respawn", _("Immediate respawn"), "bool", False, _("Player"), "", "b"),
    R("playersSleepingPercentage", "players_sleeping_percentage", _("Sleeping players needed to skip night %"), "int", 100,
      _("Player"), _("100 = everyone must sleep, 1 = one player is enough"), "b", 0, 100),
    R("fallDamage", "fall_damage", _("Fall damage"), "bool", True, _("Player")),
    R("fireDamage", "fire_damage", _("Fire damage"), "bool", True, _("Player")),
    R("drowningDamage", "drowning_damage", _("Drowning damage"), "bool", True, _("Player")),
    R("freezeDamage", "freeze_damage", _("Freeze damage"), "bool", True, _("Player")),
    R("spawnRadius", "respawn_radius", _("Respawn radius"), "int", 10, _("Player"), "", "a", 0, 1000),
    R("enderPearlsVanishOnDeath", "ender_pearls_vanish_on_death", _("Ender pearls vanish on death"), "bool", True, _("Player")),
    R("doLimitedCrafting", "limited_crafting", _("Only unlocked recipes can be crafted"), "bool", False, _("Player")),
    R("spectatorsGenerateChunks", "spectators_generate_chunks", _("Spectators generate chunks"), "bool", True, _("Player")),
    R("locatorBar", "locator_bar", _("Locator bar"), "bool", True, _("Player"), "1.21.6+"),
    R("doDaylightCycle", "advance_time", _("Daylight cycle"), "bool", True, _("World"), "", "b"),
    R("doWeatherCycle", "advance_weather", _("Weather cycle"), "bool", True, _("World"), "", "b"),
    R("mobGriefing", "mob_griefing", _("Mob griefing (creepers etc.)"), "bool", True, _("World"), "", "b"),
    R("doFireTick", None, _("Fire spread (1.21.10 and older)"), "bool", True, _("World"), _("Renamed in 1.21.11+, so it is not applied there")),
    R("randomTickSpeed", "random_tick_speed", _("Random tick speed"), "int", 3, _("World"), _("Crop growth speed and more"), "b", 0, 4096),
    R("doVinesSpread", "spread_vines", _("Vines spread"), "bool", True, _("World")),
    R("snowAccumulationHeight", "max_snow_accumulation_height", _("Max snow accumulation height"), "int", 1, _("World"), "", "a", 0, 8),
    R("waterSourceConversion", "water_source_conversion", _("Infinite water sources"), "bool", True, _("World")),
    R("lavaSourceConversion", "lava_source_conversion", _("Infinite lava sources"), "bool", False, _("World")),
    R("blockExplosionDropDecay", "block_explosion_drop_decay", _("Block explosion drop decay"), "bool", True, _("World")),
    R("mobExplosionDropDecay", "mob_explosion_drop_decay", _("Mob explosion drop decay"), "bool", True, _("World")),
    R("tntExplosionDropDecay", "tnt_explosion_drop_decay", _("TNT explosion drop decay"), "bool", False, _("World")),
    R("tntExplodes", "tnt_explodes", _("TNT explodes"), "bool", True, _("World")),
    R("projectilesCanBreakBlocks", "projectiles_can_break_blocks", _("Projectiles can break blocks"), "bool", True, _("World")),
    R("globalSoundEvents", "global_sound_events", _("Global boss sounds"), "bool", True, _("World")),
    R("doTileDrops", "block_drops", _("Block drops"), "bool", True, _("Drops")),
    R("doEntityDrops", "entity_drops", _("Entity drops (minecarts etc.)"), "bool", True, _("Drops")),
    R("doMobLoot", "mob_drops", _("Mob loot"), "bool", True, _("Drops")),
    R("doMobSpawning", "spawn_mobs", _("Natural mob spawning"), "bool", True, _("Spawning"), "", "b"),
    R("doInsomnia", "spawn_phantoms", _("Phantom spawning"), "bool", True, _("Spawning"), "", "b"),
    R("doPatrolSpawning", "spawn_patrols", _("Pillager patrol spawning"), "bool", True, _("Spawning")),
    R("doTraderSpawning", "spawn_wandering_traders", _("Wandering trader spawning"), "bool", True, _("Spawning")),
    R("doWardenSpawning", "spawn_wardens", _("Warden spawning"), "bool", True, _("Spawning")),
    R("disableRaids", "raids", _("Raids"), "bool", True, _("Spawning"), "", "a", invert=True),
    R("spawnerBlocksEnabled", "spawner_blocks_work", _("Spawner blocks work"), "bool", True, _("Spawning"), "1.21.9+"),
    R("maxEntityCramming", "max_entity_cramming", _("Max entity cramming"), "int", 24, _("Spawning"), "", "a", 0, 1000),
    R("universalAnger", "universal_anger", _("Universal anger (neutral mobs)"), "bool", False, _("Spawning")),
    R("forgiveDeadPlayers", "forgive_dead_players", _("Forgive dead players"), "bool", True, _("Spawning")),
    R("announceAdvancements", "show_advancement_messages", _("Announce advancements"), "bool", True, _("Chat & commands"), "", "b"),
    R("showDeathMessages", "show_death_messages", _("Death messages"), "bool", True, _("Chat & commands"), "", "b"),
    R("commandBlockOutput", "command_block_output", _("Command block output"), "bool", True, _("Chat & commands")),
    R("sendCommandFeedback", "send_command_feedback", _("Command feedback"), "bool", True, _("Chat & commands")),
    R("logAdminCommands", "log_admin_commands", _("Log admin commands"), "bool", True, _("Chat & commands")),
    R("reducedDebugInfo", "reduced_debug_info", _("Reduced debug info (hide coordinates)"), "bool", False, _("Chat & commands")),
    R("maxCommandChainLength", "max_command_sequence_length", _("Command chain limit"), "int", 65536, _("Chat & commands")),
    R("maxCommandForkCount", "max_command_forks", _("Command fork limit"), "int", 65536, _("Chat & commands")),
    R("commandModificationBlockLimit", "max_block_modifications", _("Command block modification limit"), "int", 32768, _("Chat & commands")),
    R("playersNetherPortalDefaultDelay", "players_nether_portal_default_delay", _("Portal delay (ticks)"), "int", 80, _("Portals")),
    R("playersNetherPortalCreativeDelay", "players_nether_portal_creative_delay", _("Portal delay in creative (ticks)"),
      "int", 0, _("Portals")),
    R("disableElytraMovementCheck", None, _("Disable elytra movement check (1.21.10 and older)"), "bool", False, _("Portals")),
]

# ---------------------------------------------------------------- Launch / manage
GC = [("aikar", _("Aikar G1 tuning (recommended)")), ("zgc", "Generational ZGC (RAM 16GB+)"), ("default", _("Java default"))]

LAUNCH: list[S] = [
    S("jvm:xms_equal", _("Start memory = max memory"), "bool", True, _("Launch"), _("Same -Xms as -Xmx (recommended)"), "b"),
    S("jvm:gc", _("GC preset"), "choice", "aikar", _("Launch"), "", "b", choices=GC),
    S("jvm:compact_headers", "Compact Object Headers", "bool", False, _("Launch"),
      _("Saves memory on Java 25+ (-XX:+UseCompactObjectHeaders)")),
    S("jvm:utf8", _("UTF-8 console"), "bool", True, _("Launch"), _("Prevents broken non-English text")),
    S("jvm:extra", _("Extra JVM arguments"), "str", "", _("Launch"), _("Separated by spaces")),
    S("launch:nogui", _("Disable server GUI (nogui)"), "bool", True, _("Launch")),
    S("launch:auto_restart", _("Restart automatically after a crash"), "bool", False, _("Launch"), _("Crash protection. Stops when you close the window"), "b"),
    S("launch:restart_delay", _("Restart delay (s)"), "int", 10, _("Launch"), "", "a", 1, 3600),
    S("launch:title", _("Console window title"), "str", "Minecraft Server", _("Launch")),
]

MANAGE: list[S] = [
    S("manage:ops", _("Operators (OP)"), "str", "", _("Players"), _("Player names separated by commas"), "b"),
    S("manage:whitelist", _("Whitelisted players"), "str", "", _("Players"), _("Player names separated by commas"), "b"),
    S("manage:icon", _("Server icon"), "str", "", _("Appearance"), _("PNG/JPG image, converted to 64×64 automatically"), "b"),
    S("manage:backup", _("Create backup script"), "bool", True, _("Extras"), _("Compressed world backups with backup.bat/.sh"), "b"),
    S("manage:backup_keep", _("Backups to keep"), "int", 10, _("Extras"), _("Old backups are deleted automatically"), "a", 1, 1000),
    S("manage:firewall", _("Firewall script"), "bool", True, _("Extras"), _("open_firewall.bat, run as administrator")),
    S("manage:shortcut", _("Desktop shortcut"), "bool", False, _("Extras"), _("Windows only"), "b"),
    S("manage:upnp", _("Automatic port forwarding (UPnP)"), "bool", True, _("Extras"),
      _("Asks your router to open the server port (UPnP, PCP or NAT-PMP) so friends outside your network can join"), "b"),
    S("manage:firewall_auto", _("Allow through Windows Firewall"), "bool", True, _("Extras"),
      _("Adds inbound rules for the server ports during install (one administrator prompt)"), "b"),
    S("manage:first_run", _("First run after install"), "bool", True, _("Extras"),
      _("Creates the world, applies game rules and ops, then stops"), "b"),
]

ALL: list[S] = PROPS + RULES + LAUNCH + MANAGE
BY_KEY = {s.key: s for s in ALL}


def defaults() -> dict:
    return {s.key: s.default for s in ALL}


def count() -> int:
    return len(ALL)
