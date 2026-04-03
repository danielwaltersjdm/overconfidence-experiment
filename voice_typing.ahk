#Requires AutoHotkey v2.0

; voice_typing.ahk
; Toggles Windows Voice Typing (Win + H) with Alt + X.
; Press Alt+X once to start dictation, press Alt+X again to stop.

; Track whether voice typing is currently active
isListening := false

!x::
{
    global isListening

    ; Send Win+H to open or close the voice typing panel
    Send "#h"

    ; Flip the toggle state
    isListening := !isListening

    ; Short delay to prevent accidental double-triggering
    Sleep 500
}
