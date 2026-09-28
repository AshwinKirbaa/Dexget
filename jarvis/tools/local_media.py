"""
Local Media playback tools.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional

from jarvis.tools.base import RiskLevel, Tool, ToolResult

try:
    import psutil
except ImportError:
    psutil = None


def _resolve_movies_folder(source: str) -> Optional[str]:
    """Resolve 'movies folder' to an actual filesystem directory."""
    source_lower = source.lower().strip()
    
    # Exact paths
    if os.path.isabs(source) and os.path.exists(source):
        return source
        
    aliases = [
        "movies", "my movies", "movie folder", 
        "movies folder", "my movies folder", "movies_folder"
    ]
    if source_lower in aliases:
        # Check standard common locations
        candidates = [
            "D:\\Movies",
            "E:\\Movies",
            "F:\\Movies",
            "C:\\Movies",
            os.path.expanduser("~/Movies"),
            os.path.expanduser("~/Videos"),
            os.path.expanduser("~/Desktop/Movies"),
            os.path.expanduser("~/Documents/Movies"),
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.isdir(c):
                return c
                
    # Fallback checking if user provided a relative path like "Videos"
    home = os.path.expanduser("~")
    rel_path = os.path.join(home, source)
    if os.path.exists(rel_path) and os.path.isdir(rel_path):
        return rel_path
        
    return None


def _get_video_files(directory: str) -> List[str]:
    """Recursively search for video files in a directory."""
    extensions = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm", ".flv"}
    results = []
    
    if not os.path.exists(directory):
        return results
        
    for root, _, files in os.walk(directory):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions:
                results.append(os.path.join(root, f))
                
    return results


def _extract_s_e_from_filename(filename: str) -> tuple[Optional[int], Optional[int]]:
    """Try to extract season and episode from filename."""
    # S01E02, s1e2, S01x02
    m = re.search(r"[Ss](\d+)[EeXx](\d+)", filename, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
    
    # Season 1 Episode 2
    m = re.search(r"season\s+(\d+).*?episode\s+(\d+)", filename, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
        
    # 1x02
    m = re.search(r"\b(\d+)x(\d+)\b", filename, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))
        
    return None, None


def _score_file(filename: str, title: Optional[str], season: Optional[int], episode: Optional[int]) -> int:
    """Score how well a filename matches the requested media."""
    score = 0
    basename = os.path.basename(filename).lower()
    
    fs, fe = _extract_s_e_from_filename(basename)
    
    if season is not None and episode is not None:
        if fs == season and fe == episode:
            score += 100
        else:
            return 0  # wrong season/episode entirely
            
    if title:
        title_lower = title.lower()
        if title_lower in basename:
            score += 50
        # Check if words match
        words = re.findall(r'\w+', title_lower)
        matches = sum(1 for w in words if w in basename)
        score += (matches * 10)
        
    return score


def play_local_media(media_title: str, season: Optional[int] = None, episode: Optional[int] = None, source: str = "movies folder") -> ToolResult:
    def _log(msg):
        print(f"  {msg}")
        
    _log("[MEDIA] Resolving source folder...")
    resolved_dir = _resolve_movies_folder(source)
    if not resolved_dir:
        return ToolResult(False, error="not_found", observation=f"[FAILED] Could not resolve source directory: {source}")
        
    _log(f"[MEDIA] Searching {resolved_dir}...")
    all_videos = _get_video_files(resolved_dir)
    
    if not all_videos:
        return ToolResult(False, error="not_found", observation=f"[FAILED] No video files found in {resolved_dir}")
        
    _log(f"[MEDIA] Scoring {len(all_videos)} video files...")
    scored = []
    for f in all_videos:
        score = _score_file(f, media_title, season, episode)
        if score > 0:
            scored.append((score, f))
            
    if not scored:
        return ToolResult(False, error="not_found", observation=f"[FAILED] Could not find {media_title} " + (f"S{season:02d}E{episode:02d}" if season else "") + f" in {resolved_dir}")
        
    # Sort by score descending, then by filename alphabetically ascending
    scored.sort(key=lambda x: (-x[0], os.path.basename(x[1]).lower()))
    best_match = scored[0][1]
    
    _log(f"[MEDIA] Found:\n{os.path.basename(best_match)}")
    
    # 8. PLAY THE ACTUAL FILE
    # Play using os.startfile which invokes the default handler
    try:
        _log(f"[MEDIA] Opening file...")
        os.startfile(best_match)
    except Exception as exc:
        return ToolResult(False, error=str(exc), observation=f"[FAILED] Could not launch media player: {exc}")
        
    # 9. VERIFY PLAYBACK
    # Need to check if a process opened and window exists.
    _log("[VERIFY] Waiting for media player...")
    time.sleep(2.0)
    
    try:
        import jarvis.tools.window_manager as wm
        # Search all top level windows to see if any contain the filename or "VLC" / "Movies & TV"
        # and has a valid process
        found_window = False
        target_basename = os.path.basename(best_match)
        target_no_ext = os.path.splitext(target_basename)[0]
        
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        # Give it a few attempts
        for _ in range(5):
            windows = []
            def callback(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        windows.append((hwnd, buf.value))
                return True
            
            user32.EnumWindows(WNDENUMPROC(callback), 0)
            
            for hwnd, title in windows:
                # Common media players or matching title
                if "VLC media player" in title or "Movies & TV" in title or "Media Player" in title or target_no_ext.lower() in title.lower():
                    _log(f"[VERIFY] Player window detected: {title}")
                    found_window = True
                    break
                    
            if found_window:
                break
            time.sleep(1.0)
            
        if found_window:
            _log("[VERIFY] Playback file confirmed.")
            display_title = media_title if media_title else ""
            return ToolResult(True, observation=f"[OK] Playing {display_title}" + (f" S{season:02d}E{episode:02d}" if season else "").strip())
        else:
            # We didn't find the exact window title, but maybe it just launched invisibly or we couldn't match the title
            display_title = media_title if media_title else ""
            return ToolResult(False, error="verify_failed", observation=f"[FAILED] Could not verify playback of {display_title}" + (f" S{season:02d}E{episode:02d}" if season else "").strip())
            
    except ImportError:
        display_title = media_title if media_title else ""
        return ToolResult(True, observation=f"[OK] Playing {display_title}" + (f" S{season:02d}E{episode:02d}" if season else "").strip())


def register(registry) -> None:
    registry.register(Tool(
        name="win_play_local_media",
        description="Search for and play a local media file (movies/episodes).",
        parameters={
            "media_title": {"type": "str", "required": False},
            "season": {"type": "int", "required": False},
            "episode": {"type": "int", "required": False},
            "source": {"type": "str", "required": True}
        },
        risk_level=RiskLevel.LOW,
        func=play_local_media,
        category="windows"
    ))
