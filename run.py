import argparse
import signal
import os, sys
import logging
import glob
import re
from sys import exit
import types
import types

# TODO :
# Game.fullName has double quotes + sometimes the trailing ) of the GAME() definition
# Prolly need a hard coded hack for machine stvbios as the real MACHINE name is stv
# equites.c : 
    #define BMPAD 8
# halleys.c : C define
    #define VIS_MINX      0
    #define VIS_MAXX      255
    #define VIS_MINY      8
    #define VIS_MAXY      (255-8)
# sg1000a.c : can't find a resolution -> 280x210 @ 59.92Hz
# hyprduel.c : C define:
    #define FIRST_VISIBLE_LINE 0
    #define LAST_VISIBLE_LINE 223
# lazercmd.c as expected values are C defines + VISIBL_AREA is on 2 lines
    #define HORZ_RES                32
    #define VERT_RES                24
    #define HORZ_CHR        8
    #define VERT_CHR                10
    #define VERT_FNT                8
# namconb1.c : C define 
    #define NAMCONB1_COLS		36 
    #define NAMCONB1_ROWS		28
# namcos22.c : C define
    #define NAMCOS22_NUM_ROWS 30
    #define NAMCOS22_NUM_COLS 40
# nss.c : C define
    #define SNES_SCR_WIDTH          256             /* 32 characters 8 pixels wide */
    #define SNES_SCR_HEIGHT         240             /* Can be 224 of 240 height (maybe we'll have switching later on) */
    #define SNES_MAX_LINES_NTSC     262             /* Maximum number of lines for NTSC systems */
    #define SNES_MAX_LINES_PAL      312             /* Maximum number of lines for PAL systems */


MACHINE_HACKS = {
    'equites.c'     :   {   'BMPAD'     : '8' },
    'halleys.c'     :   {   'VIS_MINX'  : '0',
                            'VIS_MAXX'  : '255',
                            'VIS_MINY'  : '8',
                            'VIS_MAXY'  : '(255-8)'},
    'hyprduel.c'    :   {   'FIRST_VISIBLE_LINE'    : '0',
                            'LAST_VISIBLE_LINE'     : '223'},
    'lazercmd.c'    :   {   'HORZ_RES'  : '32',
                            'VERT_RES'  : '24',
                            'HORZ_CHR'  : '8',
                            'VERT_CHR'  : '10'},
    'namconb1.c'    :   {   'NAMCONB1_COLS' : '36',
                            'NAMCONB1_ROWS' : '28'},
    'namcos22.c'    :   {   'NAMCOS22_NUM_ROWS' : '30',
                            'NAMCOS22_NUM_COLS' : '40'},
    'nss.c'         :   {   'SNES_SCR_WIDTH'        : '256',
                            'SNES_SCR_HEIGHT'       : '240',
                            'SNES_MAX_LINES_NTSC'   : '262',
                            'SNES_MAX_LINES_PAL'    : '312'}
}

MACHINE_NAME_HACKS = {
    'stvbios'   : 'stv'
}

LOGGING_LEVELS = {  'critical': logging.CRITICAL,
                    'error'   : logging.ERROR,
                    'warning' : logging.WARNING,
                    'info'    : logging.INFO,
                    'debug'   : logging.DEBUG
                }


class rootClass():
    def __init__(self, fileName):
        if not os.path.isfile(fileName):
            logging.error("{} is not a file".format(fileName))
            exit(2)
        self.fullFilePath = fileName
        # Patterns
        # Machine patterns
        self.reMACHINE_DRIVER_START = "^\s*(static)?\s*MACHINE_DRIVER_START\s*\(\s*(\w+)\s*\)"
        self.reMACHINE_DRIVER_END   = "^MACHINE_DRIVER_END$"
        self.reGAME                 = ".*GAME[BX]{0,2}\s*\((.*\))"
        
    # Awesome code from http://stackoverflow.com/a/241506
    def commentRemover(self, text):
        def replacer(match):
            s = match.group(0)
            if s.startswith('/'):
                return " " # note: a space and not an empty string
            else:
                return s
        pattern = re.compile(
            r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            re.DOTALL | re.MULTILINE
        )
        return re.sub(pattern, replacer, text)
        
    # strips and remove comments
    def cleanLine(self, text):
        return self.commentRemover(text).strip()
        
    # strips and remove comments, then return the matching groups
    def findMatchesFromPattern(self, rePattern, text):
        return re.match(rePattern, self.commentRemover(text.strip()))
        
    # Reads a file, return matching patterns
    def readFileAndFindPatterns(self, pattern):
        result = dict()
        lines = open (self.fullFilePath, "r")
        for line in lines:
            matches = self.findMatchesFromPattern(pattern, line)
            if matches : result[line] = matches
        return result
    
    # Reads a section, returns cleaned lines
    def readFileAndFindSection(self, sectionParam, sectionStart, sectionStop):
        result = []
        inSection = False
        lines = open (self.fullFilePath, "r")
        for line in lines:
            line = self.cleanLine(line)
            # Skip empty lines
            if not line : continue
            if sectionParam in line and self.findMatchesFromPattern(sectionStart, line):
                logging.debug("Found section name {} !".format(sectionParam))
                inSection = True
                continue
            if inSection and self.findMatchesFromPattern(sectionStop, line):
                logging.debug("Found section end of {} !".format(sectionParam))
                break
            if inSection: 
                logging.debug("Adding '{}' to the section content".format(line))
                result.append(self.cleanLine(line))
                
        return result
    
    # Replace machine name with hacked one
    def normalizeMachineName(self, machineName):
        if machineName in MACHINE_NAME_HACKS:
            logging.debug("DIRTY HACK : replacing machine name {} by {}".format(machineName, MACHINE_NAME_HACKS[machineName]))
            return MACHINE_NAME_HACKS[machineName]
        else:
            return machineName
    
#
# Driver
#
class Driver(rootClass):
    def __init__(self, file):
        rootClass.__init__(self, file)
        self.driver         = os.path.basename(self.fullFilePath)
        self.machines       = dict()
        self.games          = dict()
        self.importMachine  = None      # if the machine imports another one
        
        logging.debug("Initiating a new driver ! " + str(self))
        self.getMachines()
        self.getGames()
        
    def __str__(self):
        return "driver: {}".format(self.driver)
    
    def getMachines(self):
        matches = self.readFileAndFindPatterns(self.reMACHINE_DRIVER_START)
        for line, match in matches.iteritems():
            logging.debug("Found {}".format(line.rstrip()))
            machineName=match.group(2).strip()
            logging.info("New machine found: {}".format(machineName))
            self.machines[machineName] = Machine(self.fullFilePath, machineName)

    def getGames(self):
        matches = self.readFileAndFindPatterns(self.reGAME)
        for line, match in matches.iteritems():
            logging.debug("Found {}".format(line.rstrip()))
            if re.match(".*GAME_NOT_WORKING.*", line):
                logging.warning("Non working game ! Not yet accepted '{})".format(line))
                continue
            result = match.group(1).split(',')
            result = [item.strip() for item in result]
            year, game, parent, machine, input, yolo, rotation, editor, fullName = result[:9]
            self.games[game] = Game(self.fullFilePath, game, parent, machine, year, fullName, self.driver, rotation, editor, )
            logging.info("New game found: " + str(self.games[game]))
    
    
    __repr__ = __str__

#
# Machine
#
class Machine(rootClass):
    def __init__(self, sourceFile, name):
        rootClass.__init__(self, sourceFile)
        self.machine = name
        self.imported = None
        self.driver = os.path.basename(sourceFile)
        # Resolution stuff
        self.visibleX   = "0"
        self.areaX      = "0"
        self.offsetX    = "0"
        self.finalX     = "0"
        self.visibleY   = "0"
        self.areaY      = "0"
        self.offsetY    = "0"
        self.finalY     = "0"
        self.resolution = ''
        self.machineData = []
        self.machineImport = []

        logging.debug("Initiating a new machine ! " + str(self))
        self.readMachineFromDriver()
        self.parseMachine()
    
    def readMachineFromDriver(self):
        # This could have been done in Driver.getMachines() to avoid reading multiple times a same file ... well .. ,evermind
        self.machineData = self.readFileAndFindSection(self.machine, self.reMACHINE_DRIVER_START, self.reMACHINE_DRIVER_END)
        if not self.machineData : logging.error("Couldn't read data for machine {}".format(self.machine))

    def parseMachine(self):
        logging.debug("Parsing machine data ...")
        if not self.machineData : 
            logging.warning("Couldn't read data for machine {}".format(self.machine))
            return False
        for line in self.machineData:
            logging.debug("Parsing {} ...".format(line))
            # This is not the most secure way to do such a thing, but it would make regex-ing each line much more complicated
            line = self.constantToValue(line)
            # Import another machine
            matches = self.findMatchesFromPattern(".*MDRV_IMPORT_FROM\(\s*(\w+)\s*\).*", line)
            if matches :
                self.machineImport.append(matches.group(1))
                logging.info("Machine '{}': Found an import pointing to {} !".format(self.machine, self.machineImport))
                continue
            # Screen size
            matches = self.findMatchesFromPattern(".*MDRV_SCREEN_SIZE\s*\(\s*([0-9xabcdef+*]+)\s*,\s*([0-9xabcdef+*]+)\)", line)
            if matches :
                self.visibleX = self.evaluate(matches.group(1).strip())
                self.visibleY = self.evaluate(matches.group(2).strip())
                logging.info("Machine '{}': Found the screen size  {}x{}".format(self.machine, self.visibleX, self.visibleY))
                continue
            # Visible Area
            # https://regex101.com/r/YAdAJk/1
            matches = self.findMatchesFromPattern(".*MDRV_VISIBLE_AREA\s*\(\s*([0-9xabcdef+*\/\-\(\) ]+)\s*,\s*([0-9xabcdef+*\/\-\(\) ]+)\s*,\s*([0-9xabcdef+*\/\-\(\) ]+)\s*,\s*([0-9xabcdef+*\/\-\(\) ]+)\s*\)", line)
            if matches :
                self.offsetX    = self.evaluate(matches.group(1).strip())
                self.areaX      = self.evaluate(matches.group(2).strip())
                self.offsetY    = self.evaluate(matches.group(3).strip())
                self.areaY      = self.evaluate(matches.group(4).strip())
                self.finalX     = self.resolutionRound(int(self.areaX) - int(self.offsetX))
                self.finalY     = self.resolutionRound(int(self.areaY) - int(self.offsetY))
                if self.finalX != 0 and self.finalY != 0: self.resolution="{}x{}".format(self.finalX, self.finalY)
                logging.info("Machine '{}': Found the visible area {} {} {} {} ! Machine resolution is {}x{}".format(self.machine, self.offsetX, self.areaX, self.offsetY, self.areaY, self.finalX, self.finalY))
                continue
    
    def evaluate(self, value):
        value = self.convHex2Int(value)
        if not value:
            logging.debug("{} is not a value".format(value))
            return None
        if re.match("^[0-9xabcedf+* \/\-\(\)]+$", value):
            return eval(value)
        else:
            logging.critical("Couldn't eval {}".format(value))
            return None
            
    def resolutionRound(self, number):
        if (number + 1) %2 == 0: return number + 1
        else: return number
        
    def convHex2Int(self, value):
        if re.match("^0x\d+$", value):
            logging.debug("{} is a hex value".format(value))
            return str(int(value, 16))
        else:
            return value
    
    def constantToValue(self, val):
        if not self.driver in MACHINE_HACKS:
            return val
        logging.debug("{} has a define hack".format(self.driver))
        hacks   = MACHINE_HACKS[self.driver]
        ret     = val
        for const, repl in hacks.iteritems():
            ret = ret.replace(const, repl)
        logging.debug("{} : undefined turned to {}".format(self.driver, ret))
        return ret
    
    def __str__(self):
        return "name: {} - driver: {} - resolution: {}x{}".format(self.machine, self.driver, self.finalX, self.finalY)

    __repr__ = __str__
    
#
# Game
#
class Game(rootClass):
    def __init__(self, sourceFile, name, parent='', machine='', year='', fullName='', driver='', rotation='', editor=''):
        rootClass.__init__(self, sourceFile)
        self.name = name
        self.parent = parent
        self.machine = machine
        self.year = year
        self.fullName = fullName
        self.driver = driver
        self.rotation = rotation
        self.resolution = None
        self.editor = ''
        
        logging.debug("Initiating a new game ! " + str(self))
   
    def __str__(self):
        return "name: '{}' - parent: '{}' - machine: '{}' - rotation: '{}'".format(self.name, self.parent, self.machine, self.rotation)

    __repr__ = __str__
    
    
def signal_handler(signal, frame):
    print('User forced exit')
    if runner.proc:
        print('killing runner.proc')
        runner.proc.kill()
    exit(1)

#
# check argguments from command line
#

def checkArgs(args):
    logging.debug("Checking arguments ...")
    if not os.path.isdir(args.mamepath): 
        print >> sys.stderr, "{} is not a valid path".format(args.mamepath)
        return False
        
    return True

#
# Recursive function to find the resolution among imported 
#    
def findResolution(importedMachines, machinesList):
    if not isinstance(importedMachines, list): 
        logging.critical("Did not provide a list of imported machines, aborting")
        exit(2)
    if not isinstance(machinesList, dict): 
        logging.critical("Did not provide a list of machines, aborting")
        exit(2)
    
    for machineName in importedMachines:
        if machineName not in machinesList: 
            logging.warning("{} is not a valid machine !".format(machineName))
            continue
        
        machine = machinesList[machineName]
        # Does this machine have a valid resolution ?
        if machine.finalX != "0" and machine.finalY != "0":
            # YES : return it
            return "{}x{}".format(machine.finalX, machine.finalY)
        else:
            # NO : browse through its imported machines
            resolution = findResolution(machine.machineImport, machinesList)
            if resolution is not None:
                return resolution
    
    return None
        
def Tests():
    # ddragon3.c as a machine as a comment
    # namcos22.c has commented GAME(...)
    # 8080bw_drivers.c has some comments between /* ... */ before a game declaration
    # xmen.c has GAME GAMEX and non working games
    # lazercmd.c has CONST values for VISIBLE_AREA and SCREEN_SIZE => first hard coded hack ?
    # itech32.c has multiple machine imports : wcbwl165 -> wcbowl -> bloodstm -> timekill
    # midvunit.c : midvunit machine has 2 imports with sub-imports
    logging.info("Running Tests() ...")
    
    myDriver = Driver("/home/subs/git/recalbox-build-pi3/output/build/libretro-mame2003-ef38e60fecf12d5edcaea27b048c9ef72271bfa9/src/drivers/itech32.c")
    logging.debug(myDriver.machines)
    # myMachine = Machine("/home/subs/git/recalbox-build-pi3/output/build/libretro-mame2003-ef38e60fecf12d5edcaea27b048c9ef72271bfa9/src/drivers/boxer.c", "boxer")
    #~ print myMachine.convHex2Int("0x100")
    exit(0)
        
def main(args):
    loggingLevel = LOGGING_LEVELS.get( args.log_level, logging.ERROR)
    logging.basicConfig(stream=sys.stdout, level=loggingLevel, format='%(asctime)s %(levelname)s %(filename)s/%(funcName)s(%(lineno)d): %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logging.info("Specified logging level: {}".format(args.log_level))
    logging.info("Running main ...")

    # Check arguments
    if not checkArgs(args) : exit(1)
      
    if args.testing:
        logging.debug("Running tests only ...")
        Tests()
        
    machines    = dict()
    games       = dict()
    # We're all set, load everything up !
    logging.info("Gathering data from source drivers ...")
    for fileName in glob.glob(args.mamepath + "/*.c"):
        logging.debug("Parsing {} ...".format(fileName))
        myDriver = Driver(fileName)
        machines.update(myDriver.machines)
        games.update(myDriver.games)
    # print myDriver.machines # y'a un sushi avec la machine midvunit non reconnue
    logging.info("Browsing games to find their resolution ...")
    # Time to browse games and find their resolution
    for gameName, gameData in games.iteritems():
        # Machine as the resolution
        resolution = None
        normalizedMachine = gameData.normalizeMachineName(gameData.machine)
        if normalizedMachine in machines :
            # A machine can have its own resolution and still import for audio
            if machines[normalizedMachine].finalX != "0" and machines[normalizedMachine].finalY != "0" :
                resolution = "{}x{}".format(machines[normalizedMachine].finalX, machines[normalizedMachine].finalY)
            elif machines[gameData.machine].machineImport :
                resolution = findResolution(machines[gameData.machine].machineImport, machines)
        
        if resolution is None:
            print "Couldn't find resolution for {}/{}({})".format(gameData.driver, gameName, gameData.machine)
        else:
            print "{}/{} has a resolution of {}".format(gameName, gameData.driver, resolution)
    return 0
    
if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description='Arcade Resolution and rotation generator')
    parser.add_argument("-m", "--mamepath", help="Specify the path to the MAME drivers source directory", type=str, required=True)
    parser.add_argument('-l', '--log-level', help='Logging level', default=logging.ERROR)
    parser.add_argument('-s', '--separator', help='Separator used for output. Default is a single space', default=' ')
    parser.add_argument('-t', '--testing', help='run the testing mode only', default=False, action="store_true" )
    
    # parser.add_argument('-f', '--logging-file', help='Logging file name')
    args = parser.parse_args()
    

    exitcode = main(args)
