#!/usr/bin/env python

import os, sys, socket, struct, select, time
import threading
import random

if sys.platform == "win32":
    # On Windows, the best timer is time.clock()
    default_timer = time.clock
else:
    # On most other platforms the best timer is time.time()
    default_timer = time.time

ICMP_ECHO_REQUEST = 8 


class ping():
    #inside class for do ping  multithreading
    mutex = threading.Lock()  
    def _checksum(self,packet):
        value_sum = 0
        size=len(packet)
        if size%2==1:
            size+=1
            packet=packet+b'\x00'
        for idx in range(0,size,2):
            thisVal = packet[idx+1]*256 + packet[idx]
            value_sum = value_sum + thisVal
        value_sum = (value_sum >> 16)  +  (value_sum & 0xffff)
        value_sum = (value_sum >> 16)  +  (value_sum & 0xffff)
        checkSum = ~value_sum
        checkSum = checkSum & 0xffff
        checkSum = checkSum >> 8 | (checkSum << 8 & 0xff00)
        return checkSum
    
    def _receive_one_ping(self,my_socket, ID, timeout):
        """
        receive the verbose_ping from the socket.
        """
        timeLeft = timeout
        while True:
            startedSelect = default_timer()
            whatReady = select.select([my_socket], [], [], timeLeft)
            howLongInSelect = (default_timer() - startedSelect)
            if whatReady[0] == []: # Timeout
                return
    
            timeReceived = default_timer()
            recPacket, addr = my_socket.recvfrom(1024)
            icmpHeader = recPacket[20:28]
            type, code, checksum, packetID, sequence = struct.unpack(
                "bbHHh", icmpHeader
            )
            # Filters out the echo request itself. 
            # This can be tested by pinging 127.0.0.1 
            # You'll see your own request
            if type != 8 and packetID == ID:
                bytesInDouble = struct.calcsize("d")
                timeSent = struct.unpack("d", recPacket[28:28 + bytesInDouble])[0]
                return timeReceived - timeSent
            
            timeLeft = timeLeft - howLongInSelect
            #if timeLeft <= 0:
                #return
    def _send_one_ping(self,my_socket, dest_addr, ID):
        """
        Send one verbose_ping to the given >dest_addr<.
        """
        dest_addr  =  socket.gethostbyname(dest_addr)
    
        # Header is type (8), code (8), _checksum (16), id (16), sequence (16)
        my_checksum = 0
    
        # Make a dummy heder with a 0 _checksum.
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1)
        bytesInDouble = struct.calcsize("d")
        #random data packet
        data=""
        for idx in range(192 - bytesInDouble):
            data+=chr(random.randint(0,127))
        data = struct.pack("d", default_timer()) + data.encode('ASCII')
    
        # Calculate the _checksum on the data and the dummy header.
        my_checksum = self._checksum(header + data)
    
        # Now that we have the right _checksum, we put that in. It's just easier
        # to make up a new header than to stuff it into the dummy.
        header = struct.pack(
            "bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1
        )
        packet = header + data
        my_socket.sendto(packet, (dest_addr, 1)) # Don't know about the 1(The 1 means port/protocol number. The protocol number of icmp is 1)
    def _initSocket(self):
        icmp = socket.getprotobyname("icmp")
        try:
            self.my_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
        except socket.error as e:
            msg = e + (
                " - Note that ICMP messages can only be sent from processes"
                " running as root."
            )
            raise socket.error(msg)
            raise # raise the original error
    
        self.my_ID = os.getpid() 
    
    def _do_one(self,dest_addr, timeout):
        """
        Returns either the delay (in seconds) or none on timeout.
        """
        self._send_one_ping(self.my_socket, dest_addr, self.my_ID)
        delay = self._receive_one_ping(self.my_socket, self.my_ID, timeout)
        return delay

    def _ping(self):
        count=0
        self.output("start ping "+self.ping_dest_addr+".....")
        while not self._stopTag:
            result=("ping %s" % self.ping_dest_addr)
            try:
                delay  =  self._do_one(self.ping_dest_addr, self.timeout)
                if delay  ==  None:
                    #if there is no packet receive 4 times, timeout
                    for idx in range(4):
                        delay  =  self._do_one(self.ping_dest_addr, self.timeout)
                        if delay!=None:
                            break
            except socket.gaierror as e:
                self.output (result+" failed. (socket error: '%s')" % e)
                break
            except OSError as e:
                self.output (result+" failed. (socket error: '%s')" % e)
                break
            if delay==None:    
                self.output (result+" failed. (timeout within %ssec.)" % self.timeout)
            else:
                delay  =  delay * 1000
                self.output (result+" success in %0.4fms" % delay)
            count+=1
            if count==self.ping_count:
                self.stop()
            time.sleep(self.interval)
        self.ping_stoped=True
    def output(self,string):
        print(string)
    def __init__(self,ping_dest_addr,ping_count=None,timeout=2,output=None,interval=0):
        self.ping_dest_addr=ping_dest_addr
        self.ping_count=ping_count
        self.timeout=timeout
        if output!=None:
            self.output=output
        self.interval=interval
        self._initSocket()
        self.ping_stoped=False
        self._stopTag=False
        thread=threading.Thread()
        thread.run=self._ping
        thread.start()

    #stop ping
    def stop(self):
        self.my_socket.close()
        self._stopTag=True
        self.output("ping "+self.ping_dest_addr+" stoped!")
    def isStoped(self):
        return self._stopTag
            
if __name__ == '__main__':
    #test code
    test=ping("fewjiogeo.com",interval=2,timeout=2)
    test=ping("www.google.com",interval=2,timeout=2,ping_count=5)
    time.sleep(5)
    test.stop()
    all_count=0
    success_count=0
    #function used to deal with each line of ping result
    def count(ping_line):
        global all_count,success_count
        all_count+=1
        if ping_line.find("success")>=0:
            success_count+=1
    test=ping("www.facebook.com",interval=2,timeout=2,output=count)
    time.sleep(5)
    test.stop()
    # wait stop
    while(not test.isStoped()):
        time.sleep(1)
    print("ping "+test.ping_dest_addr+" "+str(all_count)+" times "+str(success_count)+" success")
    test=ping("111.111.111.111",interval=2,timeout=2)
    time.sleep(10)
    test.stop()

    