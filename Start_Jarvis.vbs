Set WshShell = CreateObject("WScript.Shell")
' Run pythonw.exe with start_app.py in the same directory as the script
WshShell.Run "pythonw.exe """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\start_app.py""", 0, False
Set WshShell = Nothing
