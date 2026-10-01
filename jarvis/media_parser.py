import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class MediaIntent:
    title: Optional[str]
    season: Optional[int]
    episode: Optional[int]
    location: Optional[str]
    drive: Optional[str]

class MediaIntentParser:
    @staticmethod
    def parse(cmd: str) -> Optional[MediaIntent]:
        cmd = cmd.strip()
        
        # We shouldn't match "play Radhimma on YouTube" here.
        if re.search(r'\b(on|in)\s+youtube(\s+music)?\b', cmd, re.IGNORECASE):
            return None
            
        # "play Dexter S07E02 from Movies"
        # "play Dexter S07E02 in movies directory"
        # "play this movie from Movies"
        # "play anime episode 12 from D drive"
        
        m = re.match(r"^play\s+(.+?)(?:\s+(?:from|in)\s+(.+))?$", cmd, re.IGNORECASE)
        if not m:
            return None
            
        query = m.group(1).strip()
        source = m.group(2).strip() if m.group(2) else None
        
        if source and source.lower().endswith(" directory"):
            source = source[:-10].strip()
            
        drive = None
        if source and source.lower().endswith(" drive"):
            drive_m = re.match(r"^([a-z])\s+drive$", source, re.IGNORECASE)
            if drive_m:
                drive = drive_m.group(1).upper()
                source = None # It's just a drive, not a specific folder
            else:
                # "D drive" or similar might be in the string, or "movies in D drive"
                pass
                
        # "anime episode 12" or "Dexter S07E02"
        title = None
        season = None
        episode = None
        
        # S07E02
        se_m = re.search(r"\b[Ss](\d+)[EeXx](\d+)\b", query, re.IGNORECASE)
        if not se_m:
            se_m = re.search(r"\bseason\s+(\d+).*?episode\s+(\d+)\b", query, re.IGNORECASE)
        if not se_m:
            se_m = re.search(r"\bepisode\s+(\d+)\b", query, re.IGNORECASE)
            if se_m:
                episode = int(se_m.group(1))
                title = query[:se_m.start()].strip() + " " + query[se_m.end():].strip()
        
        if se_m and not episode: # if we found S/E
            season = int(se_m.group(1))
            episode = int(se_m.group(2))
            title = query[:se_m.start()].strip() + " " + query[se_m.end():].strip()
            
        if not title:
            title = query
            
        title = title.strip()
        if title.lower() in ("this movie", "the movie", "the file", "the video", ""):
            title = None
            
        # Require an explicit local media signal.
        # If there's no source folder, no drive, and no season/episode pattern, it's not local media.
        if not source and not drive and not season and not episode:
            if title and not re.search(r'\b(movie|video|mp4|mkv)\b', title, re.IGNORECASE):
                return None
            
        return MediaIntent(
            title=title,
            season=season,
            episode=episode,
            location=source,
            drive=drive
        )
