import argparse
import signal
import os, sys
import logging
import glob
import re
from sys import exit

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
        self.reMACHINE_DRIVER_START = "^\s*(static)?\s*MACHINE_DRIVER_START\s*\(\s+(\w+)\s+\)"
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
        
        # Resolution stuff
        self.visibleX   = 0
        self.areaX      = 0
        self.offsetX    = 0
        self.visibleY   = 0
        self.areaY      = 0
        self.offsetY    = 0
        
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
        logging.debug("Initiating a new machine ! " + str(self))
        self.machineData = []
        self.machineImport = ''
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
            # Import another machine
            matches = self.findMatchesFromPattern(".*MDRV_IMPORT_FROM\(\s*(\w+)\s*\).*", line)
            if matches :
                logging.info("Machine '{}': Found an import pointing to {} !".format(self.machine, matches.group(1)))
                continue
            # Screen size
            matches = self.findMatchesFromPattern(".*MDRV_SCREEN_SIZE\(\s*([0-9xabcde+*]+)\s*,\s*([0-9xabcde+*]+)\)", line)
            if matches :
                logging.debug("Machine '{}': Found the screen size  {} x {}".format(self.machine, matches.group(1), matches.group(2)))
                continue
            # Visible Area
            # https://regex101.com/r/YAdAJk/1
            matches = self.findMatchesFromPattern(".*MDRV_VISIBLE_AREA\(\s*([0-9xabcde+*\-\(\) ]+)\s*,\s*([0-9xabcde+*\-\(\) ]+)\s*,\s*([0-9xabcde+*\-\(\) ]+)\s*,\s*([0-9xabcde+*\-\(\) ]+)\s*\)", line)
            if matches :
                logging.info("Machine '{}': Found the visible area {} {} {} {}".format(self.machine, matches.group(1), matches.group(2), matches.group(3), matches.group(4)))
                continue

    def __str__(self):
        return "name: {} - driver: {}".format(self.machine, self.driver)

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
        return "name: '{}' - parent: '{}' - rotation: '{}'".format(self.name, self.parent, self.rotation)

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

def Tests():
    # ddragon3.c as a machine as a comment
    # namcos22.c has commented GAME(...)
    # 8080bw_drivers.c has some comments between /* ... */ before a game declaration
    # xmen.c has GAME GAMEX and non working games
    logging.info("Running Tests() ...")
    
    myDriver = Driver("/home/subs/git/recalbox-build-pi3/output/build/libretro-mame2003-ef38e60fecf12d5edcaea27b048c9ef72271bfa9/src/drivers/ddragon3.c")
    #~ myDriver.getMachines() # Already called at construct
    logging.debug(myDriver.machines)
    #~ myMachine = Machine("/home/subs/git/recalbox-build-pi3/output/build/libretro-mame2003-ef38e60fecf12d5edcaea27b048c9ef72271bfa9/src/drivers/1942.c", "sfa3")
    exit(0)
        
def main(args):
  # print(args)
  logging.info("Running main ...")
  # Check arguments
  if not checkArgs(args) : exit(1)
  
  Tests()
  # We're all set
  for fileName in glob.glob(args.mamepath + "/*.c"):
      logging.debug("Parsing {} ...".format(fileName))
      myDriver = Driver(fileName)
  
  return 0
    
if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description='Arcade Resolution and rotation generator')
    parser.add_argument("-m", "--mamepath", help="Specify the path to the MAME drivers source directory", type=str, required=True)
    parser.add_argument('-l', '--log-level', help='Logging level', default=logging.ERROR)
    parser.add_argument('-s', '--separator', help='Separator used for output. Default is a single space', default=' ')
    # parser.add_argument('-f', '--logging-file', help='Logging file name')
    
    args = parser.parse_args()
    loggingLevel = LOGGING_LEVELS.get( args.log_level, logging.ERROR)
    logging.basicConfig(stream=sys.stdout, level=loggingLevel, format='%(asctime)s %(levelname)s %(filename)s/%(funcName)s(%(lineno)d): %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    logging.info("Specified logging level: {}".format(args.log_level))

    exitcode = main(args)
