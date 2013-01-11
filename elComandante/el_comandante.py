#!/usr/bin/env python
import sys
sys.path.insert(1, "../")
from myutils import BetterConfigParser, sClient, decode, printer
from myutils import Testboard as Testboarddefinition
from time import strftime, gmtime
import time
from shutil import copytree,rmtree
import os
import subprocess
import argparse
import environment
import xray_agente
import coolingBox_agente
import analysis_agente
import signal

los_agentes = []

def killChildren():
    print "Killing clients ..."

    # Ask the client processes to exit
    for agente in los_agentes:
        agente.request_client_exit()

    try:
        for subscription in subscriptionList:
            client.send(subscription,':prog:exit\n')
        time.sleep(1)
    except:
        pass

    # Close the subsystem client connection
    try:
        client.closeConnection()
    except:
        pass

    # Kill the client processes
    for agente in los_agentes:
        try:
            agente.kill_client()
        except:
            agente.log.error("Could not kill %s" % agente.name)

    try:
        psiChild.kill()
    except:
        print "couldn't kill psiChild"
        pass
    try:
        keithleyChild.kill()
    except:
        print "couldn't kill keithleyChild"
        pass

def handler(signum, frame):
    print 'Signal handler called with signal %s' % signum
    killChildren();
    sys.exit(0)

#signal.signal(signal.SIGINT, handler)

try:
#get timestamp
    timestamp = int(time.time())
#------------some configuration--------------

    parser = argparse.ArgumentParser()

    parser.add_argument("-c", "--config", dest="configDir",
                           help="specify directory containing config files e.g. ../config/",
                           default="../config/")

    args = parser.parse_args()
#print args.configDir
    configDir= args.configDir
    try:
        os.access(configDir,os.R_OK)
    except:
        raise Exception('configDir \'%s\' is not accessible'%configDir)
        #sys.exit()
        #raise SystemExit

#load config
    config = BetterConfigParser()
    config.read(configDir+'/elComandante.conf')
#load init
    init = BetterConfigParser()
    init.read(configDir+'/elComandante.ini')

    Directories={}

    Directories['configDir']=configDir
    Directories['baseDir']=config.get('Directories','baseDir')
    Directories['testdefDir']=config.get('Directories','testDefinitions')
    Directories['dataDir']=config.get('Directories','dataDir')
    Directories['defaultDir']=config.get('Directories','defaultParameters')
    Directories['subserverDir']=config.get('Directories','subserverDir')
    Directories['keithleyDir']=config.get('Directories','keithleyDir')
    Directories['jumoDir']=config.get('Directories','jumoDir')
    Directories['logDir']=Directories['dataDir']+'/logfiles/'

    for dir in Directories:
        #if "$configDir$" in Directories[dir]:
        Directories[dir] = os.path.abspath(Directories[dir].replace("$configDir$",configDir))
#print Directories
    try:
        os.stat(Directories['dataDir'])
    except:
        os.mkdir(Directories['dataDir'])
    try:
        os.stat(Directories['subserverDir'])
    except:
        os.mkdir(Directories['subserverDir'])

    print 'check logdirectory'
    try:
        logFiles = (os.listdir(Directories['logDir']))
        nLogFiles = len(logFiles)
        print nLogFiles
    except:
        os.mkdir(Directories['logDir'])
        print 'mkdir'
    else:
        print nLogFiles
        if nLogFiles>0:
            answer = raw_input('Do you want to overwrite \'%s\'? [y]es or [n]o\n\t'%logFiles)
            if 'y' in answer.lower():
                rmtree(Directories['logDir'])
                os.mkdir(Directories['logDir'])
            else:
                raise Exception('LogDir is not empty. Please clean logDir: %s'%Directories['logDir'])

#initialise Logger
    Logger = printer()
    Logger.timestamp = timestamp
    Logger.set_logfile('%s/elComandante.log'%(Directories['logDir']))
    Logger<<'Set LogFile to %s'%Logger.f

    #check if subsystem server is running, if not START subserver
    if not "subserver.pid" in os.listdir("/var/tmp"):
        Logger << "Starting subserver ..."
        os.system("cd %s && subserver"%(Directories['subserverDir']))
        time.sleep(0.2)
        #check again whether it is running
        if not "subserver.pid" in os.listdir("/var/tmp"):
            raise Exception("Could not start subserver")
    Logger << "Subserver is running."

#read subserver settings
    serverZiel=config.get('subsystem','Ziel')
    Port = int(config.get('subsystem','Port'))
    serverPort = int(config.get('subsystem','serverPort'))
    coolingBoxSubscription = config.get('subsystem','coolingBoxSubscription')
    keithleySubscription = config.get('subsystem','keithleySubscription')
    psiSubscription = config.get('subsystem','psiSubscription')
    xraySubscription = config.get('subsystem','xraySubscription')
    analysisSubscription = config.get('subsystem','analysisSubscription')

#create subserver client
    client = sClient(serverZiel,serverPort,"kuehlingboxcommander")

    # Create agentes that are responsible for client processes
    los_agentes.append(xray_agente.xray_agente(timestamp, Logger, client))
    los_agentes.append(analysis_agente.analysis_agente(timestamp, Logger, client))
    los_agentes.append(coolingBox_agente.coolingBox_agente(timestamp, Logger,client))

    # Make the agentes read their configuration and initialization parameters
    for agente in los_agentes:
        agente.setup_configuration(config)
        agente.setup_initialization(init)

#subscribe subscriptions
    subscriptionList = [psiSubscription]
    if init.getboolean("Keithley", "KeithleyUse"):
        subscriptionList.append(keithleySubscription)
    if init.getboolean("CoolingBox", "CoolingBoxUse"):
        subscriptionList.append(coolingBoxSubscription)
    for subscription in subscriptionList:
        client.subscribe(subscription)

    for agente in los_agentes:
        agente.subscribe()

#handler
 #directory config
    Logger.printw() #welcome message
#get list of tests to do:
    testlist=init.get('Tests','Test')
    testlist= testlist.split(',')
    while '' in testlist:
            testlist.remove('')
    print 'Testlist:',testlist

#-------------------------------------



#-----------setup Test directory function-------
    def setupdir(Testboard):
        Logger.printn()
        Logger << 'I setup the directories:'
        Logger << '\t- %s'%Testboard.testdir
        Logger << '\t  with default Parameters from %s'%Testboard.defparamdir
        #copy directory
        try:
            copytree(Testboard.defparamdir, Testboard.testdir)
            f = open( '%s/configParameters.dat'%Testboard.testdir, 'r' )
            lines = f.readlines()
            f.close()
            lines[0]='testboardName %s'%Testboard.address
            f = open( '%s/configParameters.dat'%Testboard.testdir, 'w' )
            f.write(''.join(lines))
            f.close()
        except IOError as e:
            Logger.warning("I/O error({0}): {1}".format(e.errno, e.strerror))
        except OSError as e:
            Logger.warning("OS error({0}): {1}".format(e.errno, e.strerror))
        #change address
#------------------------------------------------
    def setupParentDir(timestamp,Testboard):
            Testboard.parentDir=Directories['dataDir']+'/%s_%s_%s/'%(Testboard.module,strftime("%Y-%m-%d_%Hh%Mm",gmtime(timestamp)),timestamp)
            try:
                os.stat(Testboard.parentDir)
            except:
                os.mkdir(Testboard.parentDir)
            return Testboard.parentDir
#
    def doPSI46Test(whichtest,temp):
        client.clearPackets(psiSubscription)
#-------------start test-----------------
        for Testboard in Testboards:
            #Setup Test Directory
            Testboard.timestamp=timestamp
            Testboard.currenttest=item
            Testboard.testdir=Testboard.parentDir+'/%s_%s_%s/'%(int(time.time()),whichtest,temp)
            setupdir(Testboard)
            #Start PSI
            Testboard.busy=True
            #client.send(psiSubscription,':prog:TB1:start Pretest,~/supervisor/singleRocTest_TB1,commanderPretest')
            client.send(psiSubscription,':prog:TB%s:start %s,%s,commander_%s\n'%(Testboard.slot,Directories['testdefDir']+'/'+ whichtest,Testboard.testdir,whichtest))
            Logger.printn()
            Logger << 'psi46 at Testboard %s is now started'%Testboard.slot

        #wait for finishing
        busy = True
        while client.anzahl_threads > 0 and busy:
            time.sleep(.5)
            packet = client.getFirstPacket(psiSubscription)
            if not packet.isEmpty() and not "pong" in packet.data.lower():
                data = packet.data
                Time,coms,typ,msg = decode(data)[:4]
                if coms[0].find('STAT')==0 and coms[1].find('TB')==0 and typ == 'a' and msg=='test:finished':
                    index=[Testboard.slot==int(coms[1][2]) for Testboard in Testboards].index(True)
                    #print Testboards[index].tests
                    #print Testboards[index].currenttest
                    Testboards[index].finished()
                    Testboards[index].busy=False
                if coms[0][0:4] == 'STAT' and coms[1][0:2] == 'TB' and typ == 'a' and msg=='test:failed':
                    index=[Testboard.slot==int(coms[1][2]) for Testboard in Testboards].index(True)
                    Testboards[index].failed()
                    Testboards[index].busy=False

            packet = client.getFirstPacket(coolingBoxSubscription)
            if not packet.isEmpty() and not "pong" in packet.data.lower():
                data = packet.data
                Time,coms,typ,msg = decode(data)[:4]
                #nnprint "MESSAGE: %s %s %s %s "%(Time,typ,coms,msg.upper())
                if coms[0].find('STAT')==0 and typ == 'a' and 'ERROR' in msg[0].upper():
                    Logger.warning('jumo has error!')
                    Logger.warning('\t--> I will abort the tests...')
                    Logger.printn()
                    for Testboard in Testboards:
                        client.send(psiSubscription,':prog:TB%s:kill\n'%Testboard.slot)
                        Logger.warning('\t Killing psi46 at Testboard %s'%Testboard.slot)
                        index=[Testboard.slot==int(coms[1][2]) for Testboard in Testboards].index(True)
                        Testboard.failed()
                        Testboard.busy=False
            busy=reduce(lambda x,y: x or y, [Testboard.busy for Testboard in Testboards])
        #-------------test finished----------------


        #---------------Test summary--------------
        Logger.printv()
        for Testboard in Testboards:
                client.send(psiSubscription,':stat:TB%s?\n'%Testboard.slot)
                received=False
                while client.anzahl_threads > 0 and not received:
                    time.sleep(.1)
                    packet = client.getFirstPacket(psiSubscription)
                    if not packet.isEmpty() and not "pong" in packet.data.lower():
                        data = packet.data
                        Time,coms,typ,msg = decode(data)[:4]
                        if coms[0][0:4] == 'STAT' and coms[1][0:3] == 'TB%s'%Testboard.slot and typ == 'a':
                            received=True
                            if msg == 'test:failed':
                                Logger.warning('\tTest in Testboard %s failed! :('%Testboard.slot)
                                powercycle(Testboard)
                            elif msg == 'test:finished':
                                Logger << '\tTest in Testboard %s successful! :)'%Testboard.slot
                            else:
                                Logger << '%s %s %s %s @ %s'%(Time,coms,typ,msg,int(time.time()))
                                Logger.printn()
                                Logger.warning('\tStatus of Testboard %s unknown...! :/'%Testboard.slot)
                                powercycle(Testboard)
        Logger.printv()
        #---------------iterate in Testloop--------------

#
#-----------IV function-----------------------
    def doIVCurve(temp):
        client.clearPackets(psiSubscription)
        for Testboard in Testboards:
            Testboard.timestamp=timestamp
            Testboard.currenttest=item
            Testboard.testdir=Testboard.parentDir+'/%s_IV_%s'%(int(time.time()),temp)
            setupdir(Testboard)
            Logger << 'DO IV CURVE for Testboard slot no %s'%Testboard.slot
            #%(Testboard.address,Testboard.module,Testboard.slot),Testboard
            ivStart = float(init.get('IV','Start'))
            ivStop  = float(init.get('IV','Stop'))
            ivStep  = float(init.get('IV','Step'))
            ivDelay = float(init.get('IV','Delay'))
            ivDone = False
            client.send(keithleySubscription,':PROG:IV:START %s'%ivStart)
            client.send(keithleySubscription,':PROG:IV:STOP %s'%ivStop)
            client.send(keithleySubscription,':PROG:IV:STEP %s'%ivStep)
            client.send(keithleySubscription,':PROG:IV:DELA Y%s'%ivDelay)
            client.send(keithleySubscription,':PROG:IV:TESTDIR %s'%Testboard.testdir)
#todo check if testdir exists...
            client.send(psiSubscription,':prog:TB%s:open %s,commander_%s\n'%(Testboard.slot,Testboard.testdir,whichtest))
            time.sleep(2.0)
            client.send(keithleySubscription,':PROG:IV MEAS\n')
            while client.anzahl_threads >0 and not ivDone:
                    time.sleep(.5)
                    packet = client.getFirstPacket(keithleySubscription)
                    if not packet.isEmpty() and not "pong" in packet.data.lower():
                        #DONE
                        data = packet.data
                        Time,coms,typ,msg,fullComand = decode(data)
                        if len(coms) > 1:
                            if coms[0].find('PROG')>=0 and coms[1].find('IV')>=0 and typ == 'a' and (msg == 'FINISHED'):
                                Logger << '\t--> IV-Curve FINISHED'
                                ivDone = True
                            elif coms[0].find('IV')==0 and typ == 'q':
                                #print fullComand
                                pass
                        else:
                            pass
                        pass
                    else:
                        pass

        Logger << 'try to close TB, time.sleep for 5 seconds'
        client.send(psiSubscription,':prog:TB%s:close %s,commander_%s\n'%(Testboard.slot,Testboard.testdir,whichtest))
        time.sleep(5)
        powercycle(Testboard)

    def powercycle(Testboard):
        client.clearPackets(psiSubscription)
        Testboard.timestamp=timestamp
        whichtest='powercycle'
        Testboard.testdir=Testboard.parentDir+'/tmp/'
        setupdir(Testboard)
        Logger << 'Powercycle Testboard at slot no %s'%Testboard.slot
        Testboard.busy=True
        client.send(psiSubscription,':prog:TB%s:start %s,%s,commander_%s\n'%(Testboard.slot,Directories['testdefDir']+'/'+ whichtest,Testboard.testdir,whichtest))
        #wait for finishing
        busy = True
        while client.anzahl_threads > 0 and busy:
            time.sleep(.5)
            packet = client.getFirstPacket(psiSubscription)
            if not packet.isEmpty() and not "pong" in packet.data.lower():
                data = packet.data
                Time,coms,typ,msg = decode(data)[:4]
                if coms[0].find('STAT')==0 and coms[1].find('TB')==0 and typ == 'a' and msg=='test:finished':
                    index=[Testboard.slot==int(coms[1][2]) for Testboard in Testboards].index(True)
                    #Testboards[index].finished()
                    Testboards[index].busy=False
                    time.sleep(1)
                    try:
                        rmtree(Testboard.parentDir+'/tmp/')
                    except:
                        Logger.warning("Couldn't delete temp Dir")
                        pass
                if coms[0][0:4] == 'STAT' and coms[1][0:2] == 'TB' and typ == 'a' and msg=='test:failed':
                    index=[Testboard.slot==int(coms[1][2]) for Testboard in Testboards].index(True)
                    #Testboards[index].failed()
                    time.sleep(1)
                    Testboards[index].busy=False
                    try:
                        rmtree(Testboard.parentDir+'/tmp/')
                    except:
                        Logger.warning("Couldn't delete temp Dir")
                        pass
                    raise Exception('Could not open Testboard at %s.'%Testboard.slot)
                else:
                    pass
            busy=Testboard.busy
        #-------------test finished----------------


    def preexec():#Don't forward Signals.
        os.setpgrp()

    # Check whether the client is already running before trying to start it
    Logger << "Check whether clients are runnning ..."
    for agente in los_agentes:
        agente.check_client_running()

    for clientName in ["jumoClient","psi46handler","keithleyClient"]:
        if clientName == "jumoClient" and init.getboolean("CoolingBox", "CoolingBoxUse"):
            continue
        if clientName == "keithleyClient" and init.getboolean("Keithley", "KeithleyUse")==False:
            continue
        if not os.system("ps aux |grep -v grep| grep -v vim|grep -v emacs|grep %s"%clientName):
            raise Exception("another %s is already running. Please Close client first"%clientName)

    # Start the clients
#open psi46handler in annother terminal
    psiChild = subprocess.Popen("xterm +sb -geometry 120x20+0+900 -fs 10 -fa 'Mono' -e 'python ../psiClient/psi46master.py -dir %s -num 4'"%(Directories['logDir']), shell=True,preexec_fn = preexec)
#psiChild = subprocess.Popen("xterm +sb -geometry 160x20+0+00 -fs 10 -fa 'Mono' -e python psi46handler.py ", shell=True)

    for agente in los_agentes:
        agente.start_client(timestamp)


#open Keithley handler
    if init.getboolean("Keithley", "KeithleyUse"):
        keithleyChild = subprocess.Popen("xterm +sb -geometry 80x25+1200+1300 -fs 10 -fa 'Mono' -e %s/keithleyClient.py -d %s -dir %s -ts %s"%(Directories['keithleyDir'],config.get("keithleyClient","port"),Directories['logDir'],timestamp), shell=True,preexec_fn = preexec)
#check subscriptions?

    # Check the client subscriptions
    Logger<<"Check Subscription of the Clients:"
    time.sleep(2)
    for subscription in subscriptionList:
        if not client.checkSubscription(subscription):
            raise Exception("Cannot read from %s subscription"%subscription)
        else:
            Logger << "\t%s is answering"%subscription
    for agente in los_agentes:
        if not agente.check_subscription():
            raise Exception("Cannot read from %s subscription" % agente.subscription)
        else:
            Logger << "\t%s is answering" % agente.subscription
    Logger << "Subscriptions checked"

#-------------SETUP TESTBOARDS----------------
    Logger << 'I found the following Testboards with Modules:'
    Logger.printn()
    Testboards=[]
    for tb, module in init.items('Modules'):
        if init.getboolean('TestboardUse',tb):
            Testboards.append(Testboarddefinition(int(tb[2]),module,config.get('TestboardAddress',tb),init.get('ModuleType',tb)))
            Testboards[-1].tests=testlist
            Testboards[-1].defparamdir=Directories['defaultDir']+'/'+config.get('defaultParameters',Testboards[-1].type)
            #print Testboards[-1].defparamdir
            Logger << '\t- Testboard %s at address %s with Module %s'%(Testboards[-1].slot,Testboards[-1].address,Testboards[-1].module)
            parentDir=setupParentDir(timestamp,Testboards[-1])

            Logger << 'try to powercycle Testboard...'
            powercycle(Testboards[-1])

    Logger.printv()
    Logger << 'I found the following Tests to be executed:'
    Logger.printn()
    for item in testlist:
        if item.find('@')>=0:
            whichtest, temp = item.split('@')
        else:
            whichtest = item
            temp = 17.0
        Logger << '\t- %s at %s degrees'%(whichtest, temp)
#------------------------------------------


    Logger.printv()

#--------------LOOP over TESTS-----------------

    for item in testlist:
        Logger << item
        env = environment.environment(item, init)

        # Prepare for the tests
        Logger << "Prepare Test: %s"%item
        for agente in los_agentes:
            agente.prepare_test(item, env)
        # Wait for preparation to finish
        Logger << "Wait for preparation to finish"
        finished = False
        while not finished:
                finished = True
                for agente in los_agentes:
                    finished = finished and agente.check_finished()
                time.sleep(0.1)
        Logger << "Prepared for test %s"%item

        time.sleep(1.0)
        if item == 'Cycle':
            pass
            #doCycle()
        else:
            if init.getboolean("Keithley", "KeithleyUse"):
                client.send(keithleySubscription,':OUTP ON\n')
            if item.find('@')>=0:
                whichtest, temp = item.split('@')
            else:
                whichtest = item
                temp =17.0
            Logger.printv()
            Logger << 'I do now the following Test:'
            Logger << '\t%s at %s degrees'%(whichtest, temp)

            if whichtest == 'IV':
                doIVCurve(temp)
            else:
                doPSI46Test(whichtest,temp)

        # Execute tests
        Logger << "Execute Test: %s"%item
        for agente in los_agentes:
            agente.execute_test(item, env)

        # Wait for test execution to finish
        Logger << "Wait for test execution to finish"
        finished = False
        while not finished:
                finished = True
                for agente in los_agentes:
                    finished = finished and agente.check_finished()
                time.sleep(0.1)
        Logger << "Item %s has been finished."%item

        if init.getboolean("Keithley", "KeithleyUse"):
            client.send(keithleySubscription,':OUTP OFF\n')

        # Cleanup tests
        Logger << "start with Clean Up tests."
        for agente in los_agentes:
            agente.cleanup_test(item, env)

        # Wait for cleanup to finish
        finished = False
        while not finished:
                finished = True
                for agente in los_agentes:
                    finished = finished and agente.check_finished()
                time.sleep(0.1)
        Logger << " Clean Up tests Done"
        Logger.printv()

    # Final cleanup
    Logger << "Do final Clean Up after all tests"
    for agente in los_agentes:
        agente.final_test_cleanup()

    # Wait for final cleanup to finish
    Logger << "Wait for final clean up to finish"
    finished = False
    while not finished:
            finished = True
            for agente in los_agentes:
                finished = finished and agente.check_finished()
                time.sleep(0.1)
    Logger << "Final Clean up has been done"

#-------------Heat up---------------
    client.send(psiSubscription,':prog:exit\n')

    for agente in los_agentes:
        agente.request_client_exit()

    client.closeConnection()
    Logger << 'I am done for now!'

    time.sleep(1)
    killChildren()
    time.sleep(1)
#-------------EXIT----------------
    while client.anzahl_threads > 0:
        pass
    Logger.printv()
    Logger << 'ciao!'
    try:
        os.stat(Directories['logDir'])
    except:
        raise Exception("Couldn't find logDir %s"%Directories['logDir'])
    killChildren();

    del Logger
    for Testboard in Testboards:
            try:
                copytree(Directories['logDir'],Testboard.parentDir+'logfiles')
            except:
                raise
                #raise Exception('Could not copy Logfiles into testDirectory of Module %s\n%s ---> %s'%(Testboard.module,Directories['logDir'],Testboard.parentdir))

    rmtree(Directories['logDir'])

    #cleanup
    for Testboard in Testboards:
        try: rmtree(Testboard.parentDir+'/tmp/')
        except: pass
except:
    try:
        #TODO: Logger << 'DONE'
    except:
        pass
    killChildren()
    raise
    sys.exit(0)
