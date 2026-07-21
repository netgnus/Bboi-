' Launches the desktop cat silently (no console window).
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir_ = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "pythonw """ & dir_ & "\cat.py""", 0, False
