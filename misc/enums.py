from enum import Enum

class Side(Enum):
    NONE = None
    LEFT = "left"
    RIGHT = "right"

class ExoState(Enum):
    STOP = 0
    OPEN = 1
    CLOSE = 2

    HIDE_STOP = 5
    HIDE_OPEN = 6
    HIDE_CLOSE = 7

class WalkExo(Enum):
    EMPTY = 0 
    WALK = 1
    PAUSE = 2
    STOP = 3
    STAIRS = 4
    INC_VEL = 5
    DEC_VEL = 6

    HIDE_STOP = 7
    HIDE_WALK = 8
    RESET = 9

class RelaxFeedbackState(Enum):
    STOP = WalkExo.STOP.value
    INCREASE = WalkExo.WALK.value
    HIDE_STOP = WalkExo.HIDE_STOP.value
    RESET = WalkExo.RESET.value
    

class Cue(Enum):
    EMPTY = 0
    WALK= 1
    RELAX= 2
    STARTIN5= 3
    END= 4
    STARTEXO = 5
    HOVLEFT= 6
    HOVRIGHT= 7
    
    CLOSE_LEFT= 8
    CLOSE_RIGHT= 9
    HOVLEFT_LONG= 10
    HOVRIGHT_LONG= 11
    CLOSE = 12


DisplayText: dict = {
    Cue.EMPTY.value: '',
    Cue.WALK.value: 'walk',
    Cue.RELAX.value: 'relax',
    Cue.CLOSE_LEFT.value: 'close left',
    Cue.CLOSE_RIGHT.value: 'close right',
    Cue.CLOSE.value: 'close',

    Cue.STARTEXO.value: 'start exo',

    Cue.HOVLEFT.value: '<<<',
    Cue.HOVRIGHT.value: '>>>',
    Cue.HOVLEFT_LONG.value: '<<<<<<',
    Cue.HOVRIGHT_LONG.value: '>>>>>>',

    Cue.STARTIN5.value: 'start in 5 seconds',
    Cue.END.value: 'END'

}
