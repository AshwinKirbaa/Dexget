import re

class CommandNormalizer:
    @staticmethod
    def normalize(command: str) -> str:
        # Original command preservation for specific exact matches
        original = command.strip()
        cmd = original.lower()
        
        # Collapse whitespace
        cmd = re.sub(r"\s+", " ", cmd)
        
        # Strip trailing simple punctuation
        if re.search(r"[.!?;]+$", cmd):
            cmd = re.sub(r"[.!?;]+$", "", cmd)

        # Common spelling mistakes and aliases
        aliases = {
            r"\btoutube\b": "youtube",
            r"\bfile exlporer\b": "file explorer",
            r"\bpy charm\b": "pycharm",
            r"\byoutube music\b": "youtube music" # The router resolves "youtube music"
        }
        
        for pat, repl in aliases.items():
            cmd = re.sub(pat, repl, cmd)
            
        # Drive terminology
        # "local disk d" -> "d:\"
        cmd = re.sub(r"\blocal\s+disk\s+([a-z])\b", r"\1:\\", cmd)
        # "d drive" -> "d:\"
        cmd = re.sub(r"\b([a-z])\s+drive\b", r"\1:\\", cmd)
        
        # Folder terminology
        cmd = re.sub(r"\b([a-z0-9_]+)\s+folder\b", r"\1 directory", cmd)
        
        # Proper casing for some known applications/drives can be handled by parsers,
        # but let's ensure the drive letter is uppercase.
        def uppercase_drive(m):
            return m.group(1).upper() + ":\\"
        cmd = re.sub(r"([a-z]):\\", uppercase_drive, cmd)
        
        return cmd
