import vlc
import time

proxy_url = 'http://localhost:5003/hls.m3u8'
started = False

def callback_from_player(event, data):
    print(f"Event: {event.type}, Data: {data}")

player = vlc.Instance()
media_player = player.media_player_new()
event_manager = media_player.event_manager()

event_types = [
    vlc.EventType.MediaPlayerMediaChanged,
    vlc.EventType.MediaPlayerNothingSpecial,
    vlc.EventType.MediaPlayerOpening,
    vlc.EventType.MediaPlayerBuffering,
    vlc.EventType.MediaPlayerPlaying,
    vlc.EventType.MediaPlayerPaused,
    vlc.EventType.MediaPlayerStopped,
    vlc.EventType.MediaPlayerForward,
    vlc.EventType.MediaPlayerBackward,
    vlc.EventType.MediaPlayerEndReached,
    vlc.EventType.MediaPlayerEncounteredError,
    #vlc.EventType.MediaPlayerTimeChanged,
    #vlc.EventType.MediaPlayerPositionChanged,
    vlc.EventType.MediaPlayerSeekableChanged,
    vlc.EventType.MediaPlayerPausableChanged,
    vlc.EventType.MediaPlayerTitleChanged,
    vlc.EventType.MediaPlayerSnapshotTaken,
    vlc.EventType.MediaPlayerLengthChanged,
    vlc.EventType.MediaPlayerVout,
    vlc.EventType.VlmMediaAdded,
 	vlc.EventType.VlmMediaChanged,
 	vlc.EventType.VlmMediaInstanceStarted,
 	vlc.EventType.VlmMediaInstanceStatusEnd,
 	vlc.EventType.VlmMediaInstanceStatusError,
 	vlc.EventType.VlmMediaInstanceStatusInit,
 	vlc.EventType.VlmMediaInstanceStatusOpening,
 	vlc.EventType.VlmMediaInstanceStatusPause,
 	vlc.EventType.VlmMediaInstanceStatusPlaying,
 	vlc.EventType.VlmMediaInstanceStopped,
 	vlc.EventType.VlmMediaRemoved,
    vlc.EventType.MediaDiscovererEnded,
 	vlc.EventType.MediaDiscovererStarted,
 	vlc.EventType.MediaDurationChanged,
 	vlc.EventType.MediaFreed,
 	vlc.EventType.MediaListEndReached,
 	vlc.EventType.MediaListItemAdded,
 	vlc.EventType.MediaListItemDeleted,
 	vlc.EventType.MediaListPlayerNextItemSet,
 	vlc.EventType.MediaListPlayerPlayed,
 	vlc.EventType.MediaListPlayerStopped,
 	vlc.EventType.MediaListViewItemAdded,
 	vlc.EventType.MediaListViewItemDeleted,
 	vlc.EventType.MediaListViewWillAddItem,
 	vlc.EventType.MediaListViewWillDeleteItem,
 	vlc.EventType.MediaListWillAddItem,
 	vlc.EventType.MediaListWillDeleteItem,
 	vlc.EventType.MediaMetaChanged,
 	vlc.EventType.MediaParsedChanged,
 	vlc.EventType.MediaPlayerAudioDevice,
 	vlc.EventType.MediaPlayerAudioVolume,
]

# Attach the callback to all listed event types
# for event_type in event_types:
#    event_manager.event_attach(event_type, callback_from_player, "media_player")

def start(event, data):
    global started
    started = False
    print("Start()")
    media = player.media_new(proxy_url)
    media_player.set_media(media)
    media_player.play()

def restart(event, data):
    media_player.stop()
    player.vlm_del_media(proxy_url)
    print("Restarting in 7 seconds.")
    time.sleep(7)
    start(None, None)
    print("Called start")

start(None, None)

# Give the player some time to begin before we check if it's playing
time.sleep(3)

cur_pos = 0
prev_pos = 0
occurance_count = 0
max_count = 3
num_retries = 0
max_retries = 10

# Keep the player running
try:
    while True:
        cur_pos = media_player.get_position()
        if cur_pos == prev_pos:
            if occurance_count < max_count:
                occurance_count += 1
            else:
                print("Seems stuck")
                media_player.stop()
                restart(None, None)
                occurance_count = 0
        if media_player.is_playing():
            started = True
            num_retries = 0
        else:
            print("Not playing")
            if started:
                print("Looks like the stream has started in the past. Let's try to restart it.")
                print(f"Doubling max_retries from {max_retries} to {max_retries*2}") 
                print(f"{num_retries}")
                if num_retries < (max_retries * 2):
                    restart(None, None)
                    num_retries += 1
                else:
                    print("Exiting")
                    break
            else:
                if num_retries > max_retries:
                    print("Exiting")
                    break
                else:
                    num_retries += 1
        prev_pos = cur_pos
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping playback...")
finally:
    media_player.stop()
print("player ended")

