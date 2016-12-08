import socket, Queue
import sys
import time
import collections
from random import randint
import json
import errno
import select
import struct
import thread
import readline
import time

# 1 client sends over users 
# 3 error message something went 
# 2 server/client ACK--but server also sends the dictionary 
# 5 player moving message, sends to server 
# 6 player shooting, sends to server 
# 7 player exists 
# 4 server sends updated board -- in this case the client never sent anything, but another 
    # cleint moved/ shot
    # if the client was shot, then they can check this in the new board that was sent 
#12 server sends to client, client has no more health points so they have been kicked out of the game 
#9 will server to client updated coordinates of the bullet 
# NOTE--- client should always be listening for input from the server 
# type, src, dst, len ,data
#0 connection RTT
#10--client has quit, notifies server
#14 -- join chat 
#15 -- player A is available to chat
#16 -  show me all the available players
#17 -- chat with a player 





class Player:
    xPos = 0
    yPos = 0
    health = 2
    points = 0
    name = ""
    rtt = 0


    def __init__(self, name, dictionary = None):
        #print dictionary
        if dictionary is None:
            self.name = name
        else:
            self.name = dictionary["name"]
            self.xPos = dictionary["xPos"]
            self.yPos = dictionary["yPos"]


# Creating the board
board = [ ["."] * 10 for i in range(10) ]


availableToChat = False
p2pMode = False
list_of_clients = {}
groupChats = {}
global peerToIpPortInfo
peerToIpPortInfo = {}
peerToSend = ""
validInput = ["u", "d", "l", "r", "s"];
#global myUserName 
global newPlayer
my_rtt = 0
Coordinate = collections.namedtuple('Coordinate', 'x y')
ResponseMessage = collections.namedtuple('ResponseMessage', 'type source dest len data')


listening_port = int(sys.argv[1])
binding_port = int(sys.argv[2])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# connect to remote host
try :
    #s.connect(('comp112-01.cs.tufts.edu', port))
    s.connect(('localhost', listening_port))
except :
    print 'Unable to connect'
    sys.exit()


def noisy_thread():
    while True:
        time.sleep(3)
        #sys.stdout.write('\r'+' '*(len(readline.get_line_buffer())+2)+'\r')
        #print 'Interrupting text!'
        #sys.stdout.write('> ' + readline.get_line_buffer())
        sys.stdout.flush()



# create a new player and send to server
def initializeUser(timeOfConnection, opt_rtt = None):
    #get users name
    global myUserName
    now = time.time()
    userName = raw_input("Please enter your user name:\n")
    myUserName = userName
    #print myUserName
    # create a Player with the username
    player1 = Player(userName)
    print'Welcome, ' + userName + '!'
    #now = time.time()
    #timeOC =  time.strptime(timeOfConnection, "%Y-%m-%d %H:%M:%S,%f")
    if opt_rtt is None:
        print "time of connection" + str(timeOfConnection)
        print "current time" + str(now)
        rtt = now- float(timeOfConnection)
        print "rtt is " + str(rtt)
        if rtt < 0 :
            rtt = abs(rtt)
    else:
        rtt = opt_rtt


    player1.rtt = rtt
    bufferToSend = createBuffer(1, player1.name, "Server", len(str(rtt)), rtt)
    s.send(bufferToSend)
    return player1


# get user input and send input to server 
def playersMove(player1, userInput):
    #get a valid key input from the user 
    print "Looks like its your move!" 

    userInput = userInput.lower()
    #print player1
    if any(userInput in s for s in validInput):
        #userInput is valid 
        #print ("player's x: " + str(player1.xPos) + "y: " + str(player1.yPos) )
        # check to see if the inputted move is valid depending on where the player is 
        if player1.yPos == 0 and userInput == "u":
            print("u is an invalid move because you cant move off the game board")
            #continue
        elif player1.yPos == 9 and userInput == "d":
            print("d is an invalid move because you cant move off the game board")
            #continue
        elif player1.xPos == 0 and userInput == "l":
            print("l is an invalid move because you cant move off the game board")
            #continue
        elif player1.xPos == 9 and userInput == "r":
            print("r is an invalid move because you cant move off the game board")

            #continue
        else :
            #break
            bufferToSend = createBuffer(5, player1.name, "Server", 1, userInput)
            s.send(bufferToSend)
            return
            
    else:
        print("Sorry, your input is invalid")
        #continue

def from_string(s):
 # "Convert dotted IPv4 address to integer."
  return reduce(lambda a,b: a<<8 | b, map(int, s.split(".")))



def createBuffer(msgType, player1_name, msgDst, msgLen, msgData):   
    # once we have the correct move from the user, we sent it to the server 
    tupToSend =  ResponseMessage(type = msgType, source = player1_name, dest = msgDst, len = msgLen, data = msgData)


    bufferToSend = ""
    for item in tupToSend:
        #print("Hello " + str(item))
        bufferToSend += str(item) + "|" 
    

    return bufferToSend



# returns a ResponseMessage tuple 
def getResponseMsg(data):
    #print data
    global partialReadBuffer
    dataAsList = data.split("|", 5)

    correctList = dataAsList[:5]
    partialReadLen = len(dataAsList)
    if partialReadLen == 6:
        partialReadBuffer = dataAsList[5]


    try:
        responseMessage = ResponseMessage._make(correctList)
    except:
        print "Wrong message"
        print correctList
    
    return responseMessage


def clear_board_for_shooting():
    #print "in clear board"
    for i in range(10):
        for j in range(10):
                if board[i][j] != 'X':
                    board[i][j] = "."



def clear_board_for_moving():
    #print "in clear board"
    for i in range(10):
        for j in range(10):
            if board[i][j] !='@':
                 board[i][j] = "."


def clear_last_row():
    for i in range(10):
        if board[i][9] != 'X':
            board[i][9] = '.'



def userName_taken(player):
    # called when server sends error message 3, meaning the current username is unavilable 
    global myUserName
    newUserName = raw_input("That username is taken, please enter a different one: ")
    newUserName = newUserName.lower()
    player.name = newUserName
    myUserName = newUserName

    bufferToSend = createBuffer(1, player.name, "Server", len(str(player.rtt)), player.rtt)
    s.send(bufferToSend)


def handlePlayerDead(newPlayer):
    #global playAgain
    playAgain = "lol"
    print "Sorry you died! Thanks for playing!"
    #send message to server so we know it quits
    bufferWindow = createBuffer(5, newPlayer.name, "Server", 0, "")
    s.send(bufferWindow)
    print "Thanks for playing!"
    sys.exit(0)



def transferMessage(resMessage, peerToSend):

    if resMessage.source == peerToSend:
    	return
    bufferToSend = createBuffer(18, resMessage.source, peerToSend, len(resMessage.data), resMessage.data)
    if peerToSend not in list_of_clients:
    	return

    try:
        p_sockfd.send(bufferToSend)
    except:
        print "Unable to send chat"
        newPeerSocket = peerToIpPortInfo[peerToSend]
        p_sockfd = createASocket(newPeerSocket)
        p_sockfd.send(bufferToSend)
        list_of_clients[peerToSend] = p_sockfd 




def createASocket(peerToChat):
    #global list_of_clients
    p2p_chat = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ip = peerToChat["ip"]
    port = peerToChat["port"]
    try :
    #s.connect(('comp112-01.cs.tufts.edu', port))
        p2p_chat.connect((ip, int(port)))
    except :
        print 'Unable to connect'


    name = peerToChat["name"]
    list_of_clients[name] = p2p_chat
    return p2p_chat






def analyzeResponse(resMessage, socket_list):
    global newPlayer
    global myHealth
    global peerToIpPortInfo
    #global list_of_clients


    if resMessage.type == '0':
        my_rtt = resMessage.data
        newPlayer = initializeUser(my_rtt)
        return newPlayer
    if resMessage.type == '2':
        playersDict = json.loads(resMessage.data)
        clear_board_for_moving()
        #print ("Players" + str(playersDict))
        for username, player in playersDict.items():
            playerDict = json.loads(player)
            #print("1. " + username + " my myUserName :" + myUserName)
            if username == myUserName:
                #print ("changing player") 
                newPlayer = Player(username,playerDict)




            x = playerDict["xPos"]
            y = playerDict["yPos"]
            #print ("player's x: " + str(x) + "y: " + str(y) )
            board[y][x] = 'X'       
    elif resMessage.type == '3':
        userName_taken(newPlayer)
    elif resMessage.type == '11':
        shooting_pos = json.loads(resMessage.data)
        x = shooting_pos["xPos"]
        y = shooting_pos["yPos"]
        #print "clearing :" + str(x) + str(y)
        board[y][x] = "."
        #print board[x][y]
        printBoard()
        #clear_last_row()
        #clear_board_for_shooting()
        #need to remove the final bullet from the screen
    elif resMessage.type == '12':

        shooting_info = json.loads(resMessage.data)
        x = shooting_info["xPos"]
        y = shooting_info["yPos"]
        shooter = shooting_info["shooter"] 
        victim = shooting_info["victim"]
        board[y][x] = "X"
        if victim == myUserName :
            myHealth -= 1
            print "Player's health points is " + str(myHealth)
            print "You have been shot by " + shooter
            if myHealth == 0:
                board[y][x] = "."
                #print "YOU are DEAD"
                thread.start_new_thread(noisy_thread, ())
                handlePlayerDead(newPlayer)
        else:
            print shooter + "shot" + victim
        #need to remove the final bullet from the screen
    elif resMessage.type == '9':
        # the server is sending updated coordinates of the bullet 
        clear_board_for_shooting()
        #print('9')
        coordinatesDict = json.loads(resMessage.data)
        #print coordinatesDict
        x = coordinatesDict["xPos"]
        y = coordinatesDict["yPos"]
        board[y][x] = "@"
        # once we have the coords of the bullet, we need to add it to the array and 
        # print it out to the screen
    elif resMessage.type == '10':
        print resMessage
    elif resMessage.type == '15':
        peerPlayerDict = json.loads(resMessage.data)
        peerName = peerPlayerDict["name"]
        #list_of_clients[peerPlayerDict["name"]] = peerPlayerDict
        new_sockfd = createASocket(peerPlayerDict)
        peerToIpPortInfo[peerName] = peerPlayerDict
        socket_list.append(new_sockfd)
    elif resMessage.type == '16':
        print "-->"+ resMessage.source + ":" + resMessage.data
        reply = raw_input("reply? y/n")
        if reply == 'y':
        	peerToChat = {}
        	peerToChat["name"] = resMessage.source
        	peerToChat["sockfd"] = list_of_clients[resMessage.source]
        	sendChatMessage(newPlayer, peerToChat)
        #reply 
    elif resMessage.type == '17':
        peerToIpPortInfo = json.loads(resMessage.data)
        #list_of_clients = peerPlayerDict
        for name ,peer in peerToIpPortInfo.items():
            new_sockfd = createASocket(peer)
            socket_list.append(new_sockfd)
    elif resMessage.type == '18':
    	groupInfo = json.loads(resMessage.data)
    	groupName = groupInfo["groupName"] 
    	peerToSend = findThePeerToSend(newPlayer, groupInfo["groupChat"], groupName)
    	#transferMessage(resMessage, peerToSend)
    	if peerToSend is resMessage.source:
    		print "ITS THE THE SAME"

    	if peerToSend is not resMessage.source:
        	print "peer to send not resMessage"
        	transferMessage(resMessage, peerToSend)

    	groupChats[groupName] = groupInfo["groupChat"]
    	print "---" + groupName + "---"
    	print "-->" + resMessage.source + ":" + groupInfo["chat"]
    else:
        print " "

    return newPlayer



def playerShoot(newPlayer):
    # at this point, the player wants to shoot so we need to send to the server 
    # the starting position of the bullet
    bulletCoords = {'xPos': newPlayer.xPos, 'yPos': newPlayer.yPos}
    bullet_as_string = json.dumps(bulletCoords)
    bufferToSend = createBuffer(6, newPlayer.name, "Server", len(bullet_as_string), bullet_as_string)
    s.send(bufferToSend)


def printBoard():
    global myUserName
    # print out the current view of the board 
    print ("myUserName is "+ myUserName)
    print"Here is the current view of the game board:"
    for i in board:
        print i




def createConnection():
    time_now = time.time()
    bufferToSend = createBuffer(0, "", "Server", len(str(time)), str(time_now))
    s.send(bufferToSend)




def playerQuit(newPlayer):
    
    print(newPlayer.name)
    # notify the server that the player has quit
    bulletCoords = {'xPos': newPlayer.xPos, 'yPos': newPlayer.yPos}
    bullet_as_string = json.dumps(bulletCoords)
    
    bufferToSend = createBuffer(10, newPlayer.name, "Server", len(bullet_as_string), bullet_as_string)
    s.send(bufferToSend)

    # now need to notify all players that the player has quit
    for name, scd in list_of_clients.items():
        print ("Player is quitting, close the connection with other players")
        scd.close()
        #del list_of_clients[name]


    print "Thanks for playing!"
    sys.exit(0)






def sendListOfPlayers(newPlayer):
    #global list_of_clients
    #print "The following players are available to chat :"
    P2C = {}
    if not list_of_clients:
        print "There are no clients to chat with, tell your friends to join!"
        return ''
    else:
        print "The following players are available to chat :"
        for playerName, p2p_chat in list_of_clients.items():
            if playerName != myUserName:
                #P2C["name"] = playerName
                #P2C["sockfd"] = p2p_chat
                print playerName
        
        peerToChat = raw_input("Select a player To Chat with (or enter q to quit chat): ")
        while not peerToChat in list_of_clients.keys():
            if peerToChat == 'q':
                # player doesnt want to send chat message
                return ""
            peerToChat = raw_input("Please chose an existing player: ")


        P2C["sockfd"] = list_of_clients[peerToChat]
        P2C["name"] = peerToChat
        #sendChatMessage(P2C, newPlayer)
    return P2C

def joinExistingGroupChat(newPlayer):
    groupChat = []
    print "The following group chats are available:"
    for gc_name, g_chat in groupChats.items():
    	print gc_name + "->" +str(g_chat)

    groupName = raw_input("Select the group you want to join")
    print groupName
    while not groupName in groupChats.keys():
        if groupName == 'q':
            # player doesnt want to send chat message
            return ""
        groupName = raw_input("Please chose an existing group chat: ")

    return groupName




def createNewGroupChat(newPlayer):
    groupChat = []
    groupName = raw_input("Pick the name of your group")
    print "The following players are available:"
    for playerName, p2p_chat in list_of_clients.items():
        if playerName != myUserName:
            #P2C["name"] = playerName
            #P2C["sockfd"] = p2p_chat
            print playerName

  
    peersToChat = raw_input("Select players you would like to Chat with (or enter q to quit chat): ")
    groupChatList = peersToChat.split(" ")
    groupInfo = {}
    if len(groupChatList) == 0:
     	return
    groupChat.append(newPlayer.name)

    for peer in groupChatList:
    	if peer in list_of_clients.keys():
    	    groupChat.append(peer)
    	else:
    	    print peer +  "is not available to chat"
    groupChats[groupName] = groupChat
    return groupName


def sendListOfPlayersForGroupMessage(newPlayer):

    print "List is "
    print list_of_clients
    groupChat = []
    groupInfo = {}

    answer = raw_input("Would you like to join an existing group chat or create a new one? (o/n)?")
    print answer
    if answer == 'o':
    	groupName = joinExistingGroupChat(newPlayer)
    else:
        groupName = createNewGroupChat(newPlayer)

    print groupChats[groupName]
    if len(groupName) == 1:
    	return
    peerToChat = findThePeerToSend(newPlayer, groupChats[groupName], groupName)
    groupInfo["groupName"] = groupName
    groupInfo["peerToSend"] = peerToChat

    return groupInfo	
   


def joinChat(newPlayer):
    print "in join chat"
    print binding_port
    bufferToSend = createBuffer(14, newPlayer.name, "Server", len(str(binding_port)), binding_port)
    
    #bufferToSend = createBuffer(14, newPlayer.name, source, len(str(binding_port)), binding_port)
    s.send(bufferToSend)


def sendGroupChatMessage(newPlayer, groupChatInfo):
    global peerToIpPortInfo
    groupName = groupChatInfo["groupName"]
    chatMessage = raw_input("What do you want to say?")
    peerToSend = groupChatInfo["peerToSend"]
    messageToSend = {}
    messageToSend["chat"] = chatMessage
    messageToSend["groupChat"] = groupChats[groupName]
    messageToSend["groupName"] = groupName
    messageToSend["peerSender"] = newPlayer.name
    messageToSendAsString = json.dumps(messageToSend)

    bufferToSend = createBuffer(18, newPlayer.name, peerToSend, len(messageToSendAsString), messageToSendAsString)
    #print "socet is " + str(peerToChat["sockfd"]) + peerToChat["name"]
    p_sockfd = list_of_clients[peerToSend]
    try:
        p_sockfd.send(bufferToSend)
    except:
        print "Unable to send chat"
        newPeerSocket = peerToIpPortInfo[peerToSend]
        p_sockfd = createASocket(newPeerSocket)
        list_of_clients[peerToSend] = p_sockfd
        try:
        	p_sockfd.send(bufferToSend)
        except:
        	print "Unable to send chat"


def sendChatMessage(newPlayer, peerToChat):
    global peerToIpPortInfo
    messageToSend = raw_input("What do you want to say?")
    bufferToSend = createBuffer(16, newPlayer.name, peerToChat["name"], len(messageToSend), messageToSend)
    p_sockfd = peerToChat["sockfd"]
    try:
        p_sockfd.send(bufferToSend)
    except:
        print "Unable to send chat"
        peerName = peerToChat["name"]   
        newPeerSocket = peerToIpPortInfo[peerName]
        p_sockfd = createASocket(newPeerSocket)
        list_of_clients[peerName] = p_sockfd
        try:
        	p_sockfd.send(bufferToSend)
        except:
        	print "Unable to send chat"


def findThePeerToSend(newPlayer, groupChat, groupName):
    sizeOfList = len(groupChat) 

    index = groupChat.index(newPlayer.name)

    if index < sizeOfList - 1:
        peerToSend = groupChat[index + 1]
    else:
        peerToSend = groupChat[0]

    return peerToSend

global newPlayer    
global myHealth
global peerToChat


myHealth = 2
global partialReadBuffer
partialReadBuffer = ""
createConnection()

p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
p2p_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
        p2p_socket.bind(('localhost', binding_port))
except socket.error as msg:
        # if theres a problem binding, then the address is already in use 
        print "Another client has already claimed port:" + str(binding_port)
        print "Please reconnect with a differnt port"
        sys.exit(1)

p2p_socket.setblocking(0)
p2p_socket.listen(1)
socket_list = []
inputs = [s, sys.stdin, p2p_socket]  
outputs = []  
message_queues = {} 
while 1:
    
    #print "here"
    # Get the list sockets which are readable
    read_sockets, write_sockets, error_sockets = select.select(inputs , outputs, inputs, 2)
   # print "read_sockets are " + str(read_sockets)
    #print "socket list is " + str(socket_list)
    for sock in read_sockets:
        
        if sock is p2p_socket:
            connection, client_address = sock.accept()
            connection.setblocking(0)
            inputs.append(connection)
            message_queues[connection] = Queue.Queue()
        #print "in sock for loop"
        #incoming message from remote server
        elif sock == s:
            data = sock.recv(1054)
            if not data :
                print '\nServer disconnected'
                if sock in outputs:
                    outputs.remove(sock)
                inputs.remove(sock)
                #sys.exit()
            else :
                correct_data = partialReadBuffer + data
                newMsg = getResponseMsg(correct_data)
                newPlayer = analyzeResponse(newMsg, socket_list)
                if len(partialReadBuffer) != 0:
                    new_msg = getResponseMsg(partialReadBuffer)
                    analyzeResponse(new_msg, socket_list)
                printBoard()
        elif sock is sys.stdin:
            c = sys.stdin.read(1)
            c = c.lower()
            #print c
            if c == 's':
                playerShoot(newPlayer)
            elif c == 'q':
                playerQuit(newPlayer)
            elif c == 'j':
            	if availableToChat == False:
                    availableToChat = True
                    joinChat(newPlayer)
                else:
                    print "You're already available to chat! No need to join again."
            elif c == 'c':
            	if (availableToChat):
                    inputs.remove(sys.stdin)
                    thread.start_new_thread(noisy_thread, ())
                    peerToChat = sendListOfPlayers(newPlayer)
                    if peerToChat != "":
                        sendChatMessage(newPlayer, peerToChat)
                    inputs.append(sys.stdin)
                else:
                    print "Please type j to enable the chat feature" 
            elif c == 'g':
            	inputs.remove(sys.stdin)
                thread.start_new_thread(noisy_thread, ())
                groupChatInfo = sendListOfPlayersForGroupMessage(newPlayer)
                if groupChatInfo:
                    sendGroupChatMessage(newPlayer, groupChatInfo)

                inputs.append(sys.stdin)
            else:
                playersMove(newPlayer, c) 
            if c != 'c':
                printBoard()
        else:
            data = sock.recv(1054)
            if not data:
                if sock == s:
                    print '\n There was an error with the server'
                else:
                    print '\n There was an error with the peer, removing them'
                    sock_ip = sock.getpeername()[0]
                    for name, peerInfo in peerToIpPortInfo.items():
                    	if peerInfo["ip"] is sock_ip:
                    		if name in list_of_clients:
                    			del list_of_clients[name]
                    if sock in outputs:
                        outputs.remove(sock)
                    inputs.remove(sock)
            else :
                correct_data = partialReadBuffer + data
                newMsg = getResponseMsg(correct_data)
                newPlayer = analyzeResponse(newMsg, socket_list)
                if len(partialReadBuffer) != 0:
                    new_msg = getResponseMsg(partialReadBuffer)
                    analyzeResponse(new_msg, socket_list)
    for s in write_sockets:
        try:
            next_msg = message_queues[s].get_nowait()
        except Queue.Empty:
            outputs.remove(s)
                #del message_queues[s]
        else:
            s.send(next_msg)
    for s in error_sockets:
        socket_list.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()
        del message_queues[s]





