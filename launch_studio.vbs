Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

repoDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonwPath = repoDir & "\.venv\Scripts\pythonw.exe"
setupMarker = repoDir & "\tools\.setup_complete"

shell.CurrentDirectory = repoDir

If fso.FileExists(pythonwPath) And fso.FileExists(setupMarker) Then
    shell.Run """" & pythonwPath & """ -m backend.desktop --silent", 0, False
Else
    shell.Run "cmd.exe /c """"" & repoDir & "\run.bat""""", 1, False
End If
