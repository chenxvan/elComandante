#
# This program controls the PSI46-Testboards using the standard psi46expert software and executes Tests or opens and closes the TB
# it should work for N Testboards
# 
import sys
sys.path.insert(1, "../")
from myutils import sClient, printer, decode, BetterConfigParser
from threading import Thread
import subprocess
import sys
import argparse
import signal
import select
from time import sleep

#------------some configuration--------------
parser = argparse.ArgumentParser()

parser.add_argument("-c", "--config", dest="configDir",
                       help="specify directory containing config files e.g. ../config/",
                       default="../config/")
parser.add_argument("-dir","--directory", dest="loggingDir",
                        help="specify directory containing all logging files e.g. ../DATA/logfiles/",
                        default="../DATA/logfiles")
parser.add_argument("-num","--numTB", dest="numTB",
                        help="specify the number of Testboards in use",
                        default="1")
#parse args and setup logdir
args = parser.parse_args()
Logger = printer()
Logger.set_name("Psi46Log")
Logger.set_prefix('')
Logger.set_logfile('%s/psi46Handler.log'%(args.loggingDir))
#Logger <<'ConfigDir: "%s"'%args.configDir
configDir= args.configDir
numTB = int(args.numTB)
#load config
config = BetterConfigParser()
config.read(configDir+'/elComandante.conf')
#config
serverZiel=config.get('subsystem','Ziel')
Port = int(config.get('subsystem','Port'))
serverPort = int(config.get('subsystem','serverPort'))
psiSubscription = config.get('subsystem','psiSubscription')
#construct
client = sClient(serverZiel,serverPort,"psi46")
#subscribe
client.subscribe(psiSubscription)
#----------------------------------------------------

#handler
def handler(signum, frame):
    Logger << 'Close Connection'
    client.closeConnection()
    #Logger << 'Signal handler called with signal', signum
signal.signal(signal.SIGINT, handler)

#color gadget
def colorGenerator():
    list=['green','blue','magenta','cyan']
    i=0
    while True:
        yield list[i]
        i = (i+1)%len(list)

class TBmaster(object):
    def __init__(self, TB, client, psiSubscription, Logger, color='black'):
        self.TB = TB
        self.client = client
        self.psiSubscription = psiSubscription
        self.color = color
        self.Logger = Logger
        self.TBSubscription = '/TB%s'%self.TB
        self.client.subscribe(self.TBSubscription)

    def _spawn(self,executestr):
        self.proc = subprocess.Popen([executestr,''], shell = True, stdout = subprocess.PIPE, stdin = subprocess.PIPE)
        busy[self.TB] = True

    def _kill(self):
        try:
            self.proc.kill()
            self.Logger.warning("PSI%s KILLED"%self.TB)
        except:
            self.Logger.warning("nothing to be killed")

    def _abort(self):
        self.Logger.warning('ABORT!')
        self._kill()
        Abort[self.TB] = False
        return True

    def _resetVariables(self):
        busy[self.TB] = False
        failed[self.TB] = False
        TestEnd[self.TB] = False
        DoTest[self.TB] = False
        ClosePSI[self.TB] = False
        Abort[self.TB] = False

    def _readAllSoFar(self, retVal = ''): 
        while (select.select([self.proc.stdout],[],[],0)[0]!=[]) and self.proc.poll() is None:   
            retVal += self.proc.stdout.read(1)
        return retVal

    @staticmethod
    def findError(stat):
        return any([Error in stat for Error in ['error','Error','anyOtherString']])

    def _readout(self):
        failed = False
        self.Logger << '>>> Aquire Testboard %s <<<'%self.TB
        while self.proc.poll() is None and ClosePSI[self.TB]==False:
            if Abort[self.TB]:
                failed = self._abort()
            lines = ['']
            lines = self._readAllSoFar(lines[-1]).split('\n')
            for a in range(len(lines)-1):
                line=lines[a]
                hesays=line.rstrip()
                self.client.send(self.TBSubscription,'%s\n'%hesays)
                self.Logger.printcolor("psi46@TB%s >> %s"%(self.TB,hesays),self.color)
                if self.findError(line.rstrip()):
                    self.Logger << 'The following error triggerd the exception:'
                    self.Logger.warning(line.rstrip())
                    failed=True
                    self._kill()
                if 'command not found' in line.strip():
                    self.Logger.warning("psi46expert for TB%s not found"%self.TB)
                if Abort[self.TB]:
                    failed = self._abort()
        self.Logger << '>>> Release Testboard %s <<<'%self.TB
        TestEnd[self.TB] = True
        busy[self.TB] = False
        return failed

    def _answer(self):
        if failed[self.TB]:
            self.client.send(self.psiSubscription,':STAT:TB%s! test:failed\n'%self.TB)
            self.Logger.warning('Test failed in TB%s'%self.TB)
        else:
            self.client.send(self.psiSubscription,':STAT:TB%s! test:finished\n'%self.TB)
            self.Logger << ':Test finished in TB%s'%self.TB

    def executeTest(self,whichTest,dir,fname):
        self._resetVariables()
        self.Logger << 'executing psi46 %s in TB%s'%(whichTest,self.TB)
        executestr='psi46expert -dir %s -f %s -r %s.root -log %s.log'%(dir,whichTest,fname,fname)
        self._spawn(executestr)
        failed[self.TB]=self._readout()
        self._answer()

    def openTB(self,dir,fname):
        self._resetVariables()
        Logger << 'open TB%s'%(self.TB)
        executestr='psi46expert -dir %s -r %s.root -log %s.log'%(dir,fname,fname)
        self._spawn(executestr)
        failed[self.TB]=self._readout()
        while not ClosePSI[self.TB]:
            pass
        self.Logger << 'CLOSE TB %s HERE'%(self.TB)
        self.proc.communicate(input='exit\n')[0] 
        self.proc.poll()
        if (None == self.proc.returncode):
            try:
                self.proc.send_signal(signal.SIGINT)
            except:
                slef.Logger << 'Process already killed'
        self._answer()



#Globals
global busy
global failed
global TestEnd
global DoTest
global ClosePSI
global Abort

#numTB = 4

busy = [False]*numTB
failed = [False]*numTB
TestEnd = [False]*numTB
DoTest=[False]*numTB
ClosePSI=[False]*numTB
Abort=[False]*numTB

End=False
#MAINLOOP
color = colorGenerator()
print 'PSI Master'

#ToDo:
#initGlobals(numTB)
#init TBmasters:
TBmasters=[]
for i in range(numTB):
    TBmasters.append(TBmaster(i, client, psiSubscription, Logger, next(color)))

#RECEIVE COMMANDS (mainloop)
while client.anzahl_threads > 0 and not End:
    sleep(.5)
    packet = client.getFirstPacket(psiSubscription)
    if not packet.isEmpty() and not "pong" in packet.data.lower():
        time,coms,typ,msg,cmd = decode(packet.data)
        #Logger << time,coms,typ,msg
        #Logger << cmd
        if coms[0].find('PROG')==0 and coms[1].find('TB')==0 and coms[2].find('OPEN')==0 and typ == 'c':
            #Logger << msg
            splittedMsg =msg.split(',')
            if len(splittedMsg) !=2:
                print "couldnt convert Msg: %s --> %s"%(msg,splittedMsg)
                raise Exception
            dir, fname = splittedMsg
            TB=int(coms[1][2])
            if not busy[TB]:
                DoTest[TB] = Thread(target=TBmasters[TB].openTB, args=(dir,fname,))
                DoTest[TB].start()

        elif coms[0].find('PROG')==0 and coms[1].find('TB')==0 and coms[2][0:5] == 'CLOSE' and typ == 'c':
            if len(coms[1])>=3:
                TB=int(coms[1][2])
                Logger << 'trying to close TB...'
                ClosePSI[TB]=True

        elif coms[0].find('PROG')==0 and coms[1][0:2] == 'TB' and coms[2][0:5] == 'START' and typ == 'c':
            whichTest,dir,fname=msg.split(',')
            TB=int(coms[1][2])
            if not busy[TB]:
                #Logger << whichTest
                Logger << 'got command to execute %s in TB%s'%(whichTest,TB)
                DoTest[TB] = Thread(target=TBmasters[TB].executeTest, args=(whichTest,dir,fname,))
                DoTest[TB].start()
                client.send(psiSubscription,':STAT:TB%s! %s:started\n'%(TB,whichTest))
                busy[TB]=True
            else:
                client.send(psiSubscription,':STAT:TB%s! busy\n'%TB)

        elif coms[0][0:4] == 'PROG' and coms[1][0:2] == 'TB' and coms[2][0:4] == 'KILL' and typ == 'c':
            TB=int(coms[1][2])
            if not DoTest[TB]:
                Logger << 'nothing to be killed!'
            else:
                failed[TB]=True
                busy[TB]=False
                Abort[TB]=True
                Logger.warning('killing TB%s...'%TB)
                
        elif coms[0].find('PROG')==0 and coms[1].find('EXIT')==0 and typ == 'c':
            Logger << 'exit'
            if not reduce(lambda x,y: x or y, busy):
                End = True
            else:
                for i in range(0,numTB):
                    if busy[i]: client.send(psiSubscription,':STAT:TB%s! busy\n'%i)

        elif coms[0][0:4] == 'STAT' and coms[1][0:2] == 'TB' and typ == 'q':
            TB=int(coms[1][2])
            if busy[TB]:
                client.send(psiSubscription,':STAT:TB%s! busy\n'%TB)
            elif failed[TB]:
                client.send(psiSubscription,':STAT:TB%s! test:failed\n'%TB)
            elif TestEnd[TB]:
                client.send(psiSubscription,':STAT:TB%s! test:finished\n'%TB)
            else:
                client.send(psiSubscription,':STAT:TB%s! status:unknown\n'%TB)
        else:
            Logger << 'unknown command: ', coms, msg
    else:
        pass
        #Logger << 'waiting for answer...\n'

for i in range(0,numTB):
    if failed[i]: client.send(psiSubscription,':STAT:TB%s! test:failed\n'%i)
    elif TestEnd[i]: client.send(psiSubscription,':STAT:TB%s! test:finished\n'%i)

client.send(psiSubscription,':prog:stat! exit\n')    
print 'exiting...'
client.closeConnection()

#END
while client.anzahl_threads > 0: 
    Logger << 'waiting for client to be closed...'
    client.closeConnection()
    sleep(0.5)
    pass
Logger << 'done'
