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
        
    # strips and remove comments, then return the matching groups
    def findMatchesFromPattern(self, rePattern, text):
        return re.match(rePattern, self.commentRemover(text.strip()))
        
    # Reads a file, return matching patterns
    def readFileAndFindPatterns(self, fileName, pattern):
        result = dict()
        lines = open (fileName, "r")
        for line in lines:
            matches = self.findMatchesFromPattern(pattern, line)
            if matches : result[line] = matches
        return result
#
# Driver
#
class Driver(rootClass):
    def __init__(self, file):
        if not os.path.isfile(file):
            logging.error("{} is not a file".format(file))
            exit(2)
        self.file           = os.path.basename(file)
        self.fullFilePath   = file
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
        
        # Patterns
        self.reMACHINE_DRIVER_START = "^\s*(static)?\s*MACHINE_DRIVER_START\s*\(\s+(\w+)\s+\)"
        self.reGAME                 = ".*GAME[BX]{0,2}\((.*\))"
        
        logging.debug("Initiating a new driver ! " + str(self))
        self.getMachines()
        self.getGames()
        
    def __str__(self):
        return "driver: {}".format(self.driver)
    
    def getMachines(self):
        matches = self.readFileAndFindPatterns(self.fullFilePath, self.reMACHINE_DRIVER_START)
        for line, match in matches.iteritems():
            logging.debug("Found {}".format(line.rstrip()))
            machineName=match.group(2).strip()
            logging.info("Adding new machine: {}".format(machineName))
            self.machines[machineName] = Machine(machineName, self.driver)

    def getGames(self):
        matches = self.readFileAndFindPatterns(self.fullFilePath, self.reGAME)
        for line, match in matches.iteritems():
            logging.debug("Found {}".format(line.rstrip()))
            result = match.group(1).split(',')
            map(str.strip, result)
            year, game, parent, machine, input, yolo, rotation, fullName = result[:8]
            self.games[game] = Game(game, parent, machine, year, fullName, self.driver, rotation)
            logging.info("New game found: " + str(self.games[game]))
    
    
    __repr__ = __str__

#
# Machine
#
class Machine(rootClass):
    def __init__(self, name, driver):
        self.name = name
        self.imported = None
        self.fullPathDriver = driver # path + file name to the driver file
        self.driver = os.path.basename(driver)
        logging.debug("Initiating a new machine ! " + str(self))
    
        #~ def readData
   
    def __str__(self):
        return "name: {} - driver: {}".format(self.name, self.driver)

    __repr__ = __str__
    
#
# Game
#
class Game(rootClass):
    def __init__(self, name, parent='', machine='', year='', fullName='', driver='', rotation=''):
        self.name = name
        self.parent = parent
        self.machine = machine
        self.year = year
        self.fullName = fullName
        self.driver = driver
        self.rotation = rotation
        self.resolution = None
        
        logging.debug("Initiating a new game ! " + str(self))
    

   
    def __str__(self):
        return "name: {} - parent: {} - rotation: {}".format(self.name, self.parent, self.rotation)

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
    myDriver = Driver("/home/subs/git/recalbox-build-pi3/output/build/libretro-mame2003-ef38e60fecf12d5edcaea27b048c9ef72271bfa9/src/drivers/namcos22.c")
    #~ myDriver.getMachines() # Already called at construct
    logging.debug(myDriver.machines)
    myMachine = Machine("sfiii", "/home/subs/git/recalbox-build-pi3/output/build/libretro-mame2003-ef38e60fecf12d5edcaea27b048c9ef72271bfa9/src/drivers/1942.c")
        
def main(args):
  # print(args)
  logging.info("Running main ...")
  # Check arguments
  if not checkArgs(args) : exit(1)
  
  Tests()
  # We're all set
  # for file in glob.glob(args.)
  
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
