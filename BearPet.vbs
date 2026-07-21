' Launches the desktop teddy bear silently (no console window).
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir_ = fso.GetParentFolderName(WScript.ScriptFullName)
sh.Run "pythonw """ & dir_ & "\bear.py""", 0, False
