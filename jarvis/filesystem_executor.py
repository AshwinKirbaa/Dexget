import os
import glob
from typing import Dict, Any, Optional

def get_available_drives():
    import string
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]

def get_known_folders():
    home = os.path.expanduser("~")
    return {
        "desktop": os.path.join(home, "Desktop"),
        "documents": os.path.join(home, "Documents"),
        "downloads": os.path.join(home, "Downloads"),
        "pictures": os.path.join(home, "Pictures"),
        "music": os.path.join(home, "Music"),
        "videos": os.path.join(home, "Videos"),
    }

def execute_filesystem_route(route_args: Dict[str, Any], context: Dict[str, Any], on_progress, registry=None) -> Dict[str, Any]:
    """Execute a parsed filesystem command deterministically."""
    intent = route_args.get("intent")
    target_name = route_args.get("target_name")
    location = route_args.get("location")
    location_type = route_args.get("location_type")
    if registry is None:
        from jarvis.agent.tool_registry import ToolRegistry
        from jarvis.tools.filesystem import register
        registry = ToolRegistry()
        register(registry)
    
    if on_progress:
        on_progress(f"[PARSE] action={route_args.get('action')}, target={target_name}, location={location or 'UNSPECIFIED'}")
        
    if intent == "DRIVE_OPEN":
        if os.path.exists(location):
            if on_progress:
                on_progress(f"[ACT] Opening {location}")
            import subprocess
            subprocess.Popen(['explorer', location])
            if os.path.isdir(location):
                context["current_directory"] = location
                context["last_opened_directory"] = location
            # We skip full verification for now, assume os.startfile worked if it exists
            return {"success": True, "observation": f"Opened {location}"}
        else:
            return {"success": False, "observation": f"Drive {location} not found."}
            
    def _resolve_location(loc: str, loc_type: str) -> Optional[str]:
        if not loc:
            return context.get("current_directory") or os.path.join(os.path.expanduser("~"), "Desktop")
        if loc_type == "DRIVE" or os.path.isabs(loc) or loc.endswith(':\\'):
            if os.path.exists(loc):
                return loc
            return None
            
        known = get_known_folders()
        if loc.lower() in known:
            return known[loc.lower()]
            
        # We need to search for this folder across the system
        search_roots = []
        if context.get("current_directory"):
            search_roots.append(context.get("current_directory"))
        search_roots.extend(list(known.values()))
        search_roots.extend(get_available_drives())
        
        target_lower = loc.lower().replace(" folder", "").replace(" directory", "").strip()
        
        for root in search_roots:
            if not os.path.exists(root): continue
            
            if os.path.basename(root).lower() == target_lower:
                return root
                
            try:
                for dirpath, dirnames, _ in os.walk(root):
                    depth = dirpath[len(root):].count(os.sep)
                    if depth > 3:
                        del dirnames[:]
                        continue
                    for d in dirnames:
                        if d.lower() == target_lower:
                            return os.path.join(dirpath, d)
            except Exception:
                pass
                
        # If explicitly requested but not found, DO NOT fallback.
        return None
            
    if intent == "FILESYSTEM_OPEN":
        # Strategy:
        search_roots = []
        if location:
            search_roots = [_resolve_location(location, location_type)]
        else:
            if context.get("current_directory"):
                search_roots.append(context.get("current_directory"))
            search_roots.extend(list(get_known_folders().values()))
            search_roots.extend(get_available_drives())
            
        candidates = []
        target_name_lower = target_name.lower() if target_name else ""
        
        for root in search_roots:
            if not os.path.exists(root):
                continue
                
            if os.path.basename(root).lower() == target_name_lower:
                candidates.append(root)
                break
                
            if on_progress:
                on_progress(f"[SEARCH] Searching {root} for {route_args.get('target_type').lower()} {target_name}")
            
            # Bounded recursive search (max depth 2 for drives to avoid hanging)
            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    # Check depth
                    depth = dirpath[len(root):].count(os.sep)
                    if root.endswith(":\\") and depth > 2:
                        del dirnames[:]
                        continue
                    
                    if route_args.get("target_type") in ["DIRECTORY", "UNSPECIFIED"]:
                        for d in dirnames:
                            if d.lower() == target_name_lower:
                                candidates.append(os.path.join(dirpath, d))
                    if route_args.get("target_type") in ["FILE", "UNSPECIFIED"]:
                        for f in filenames:
                            if f.lower() == target_name_lower:
                                candidates.append(os.path.join(dirpath, f))
                                
                    # Stop if we found a match in this root
                    if len(candidates) > 0:
                        break
                if len(candidates) > 0:
                    break
            except Exception as e:
                pass
                
        if len(candidates) == 1:
            match = candidates[0]
            if on_progress:
                on_progress(f"[FOUND] {match}")
                on_progress(f"[ACT] Opening {match}")
            import subprocess
            subprocess.Popen(['explorer', match])
            if os.path.isdir(match):
                context["current_directory"] = match
                context["last_opened_directory"] = match
            return {"success": True, "observation": f"Opened {match}."}
        elif len(candidates) > 1:
            if on_progress:
                on_progress("[RESULT] AMBIGUOUS")
            cand_str = "\n".join([f"{i+1}. {c}" for i, c in enumerate(candidates)])
            return {"success": False, "observation": f"I found multiple matches:\n{cand_str}\nWhich one should I open?"}
        else:
            if on_progress:
                on_progress("[RESULT] NOT_FOUND")
            loc_str = location if location else "the system"
            return {"success": False, "observation": f"I couldn't find '{target_name}' in {loc_str}."}

    if intent == "FILESYSTEM_SEARCH":
        loc = _resolve_location(location, location_type)
        if not loc:
            return {"success": False, "observation": f"I couldn't find the folder '{location}' to search in."}
        if on_progress:
            on_progress(f"[SEARCH] Searching {loc} for {target_name}")
            
        found = []
        target_lower = target_name.lower()
        if target_lower.endswith('s'): target_lower = target_lower[:-1]
        
        try:
            for dirpath, dirnames, filenames in os.walk(loc):
                if os.path.basename(dirpath).lower() == target_lower:
                    if dirpath not in found: found.append(dirpath)
                    
                depth = dirpath[len(loc):].count(os.sep)
                if depth > 3:
                    del dirnames[:]
                    continue
                for f in filenames + dirnames:
                    if target_lower in f.lower():
                        found.append(os.path.join(dirpath, f))
        except Exception:
            pass
            
        if found:
            if on_progress:
                on_progress(f"[FOUND] {len(found)} matches")
            res_str = "\n".join(found[:10])
            if len(found) > 10: res_str += "\n... and more"
            return {"success": True, "observation": f"Found {len(found)} matches:\n{res_str}"}
        return {"success": False, "observation": f"Found no matches for {target_name} in {loc}"}

    if intent == "FILESYSTEM_CREATE":
        loc = _resolve_location(location, location_type)
        if not loc:
            return {"success": False, "observation": f"I couldn't find the folder '{location}' to create {target_name} inside."}
        path = os.path.join(loc, target_name)
        try:
            tool = "fs_create_file" if route_args.get("target_type") == "FILE" else "fs_create_directory"
            result = registry.execute(tool, path=path)
            if not result.success:
                return result.to_dict()
            if on_progress:
                on_progress(f"[ACT] Created {path}")
            context["current_directory"] = loc
            return {"success": True, "observation": f"Created {path}"}
        except Exception as e:
            return {"success": False, "observation": f"Failed to create {path}: {e}"}

    if intent == "FILESYSTEM_DELETE":
        loc = _resolve_location(location, location_type)
        if not loc:
            return {"success": False, "observation": f"I couldn't find the folder '{location}' containing the item to delete."}
        
        if os.path.basename(loc).lower() == target_name.lower():
            target_path = loc
        else:
            target_path = os.path.join(loc, target_name)
        
        if os.path.exists(target_path):
            try:
                result = registry.execute("fs_delete_file", path=target_path)
                if not result.success:
                    return result.to_dict()
                if on_progress:
                    on_progress(f"[ACT] Deleted {target_path}")
                # Reset context if we just deleted the current directory
                if target_path == context.get("current_directory"):
                    context["current_directory"] = os.path.dirname(target_path)
                return {"success": True, "observation": f"Deleted {target_path}"}
            except Exception as e:
                return {"success": False, "observation": f"Failed to delete {target_path}: {e}"}
        else:
            return {"success": False, "observation": f"Could not find {target_path} to delete."}

    if intent == "FILESYSTEM_LIST":
        loc = _resolve_location(location, location_type)
        if not loc:
            return {"success": False, "observation": f"I couldn't find the folder '{location}' to list its contents."}
        if on_progress:
            on_progress(f"[ACT] Listing {loc}")
        try:
            items = os.listdir(loc)
            res_str = "\n".join(items[:20])
            if len(items) > 20: res_str += "\n... and more"
            return {"success": True, "observation": f"Contents of {loc}:\n{res_str}"}
        except Exception as e:
            return {"success": False, "observation": f"Failed to list {loc}: {e}"}
