# Comp 112 Final Project----client/server shooting game with chat/group chat capabilities
# Written by: Sosena Bekele and Becky Cutler
# 12/14/17




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
import threading




############ Message Types #################
# Type 0: used to calculate the rtt of the player
# Type 1: c sends to s the new player info
# Type 2 : (from the server) ack + send back the dictioanry
# Type 3: error message (i.e. user name is taken)
# Type 4 : send back board after another client moves/shoot 
# type 5 : player moving message (from c to s)
# type 6: player shooting message (from c to s)
# Type 7: player exit
# Type 8: player dies 
# Type 9 : sever sends updated coordinate of bullets
# Type 10: shooting message from  telling the client who was shot
# Type 11: s sends c the coords of the bullet to be removed from the baord
# Type 15: s sends to c notification that a new player is available to chat
# Type 14: a player is now available to chat, tell the server
# Type 16: print out the chat from the source
# Type 17: s sends to c a list of the connected peers
# Type 18: client sends a (group???) message to peer
# Type 19: client tried to chat with a peer that recently quit
# Type 20: Dummy message




class Player:
    xPos = 0
    yPos = 0
    health = 5
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



# global variables
availableToChat = False
pickAPeerToChatWithMode = False
chatMode = False
readyToChat = False
serverUp = True
p2pMode = False
list_of_clients = {}
groupChats = {}
global peerToIpPortInfo
peerToIpPortInfo = {}
peerToSend = ""
validInput = ["u", "d", "l", "r", "s"]
avatars = ['X', 'O', '#']
myAvatar = " "
global myUserName 
global newPlayer
global myHealth
global peerToChat
my_rtt = 0
Coordinate = collections.namedtuple('Coordinate', 'x y')
ResponseMessage = collections.namedtuple('ResponseMessage', 'type source dest len data')




# getting the necessary info from the user
listening_port = int(sys.argv[1])
binding_port = int(sys.argv[2])
my_rtt = float(sys.argv[3])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
# connect to remote host
try :
   s.connect(('comp112-01', listening_port))
except :
    print 'Unable to connect 2'
    sys.exit()




def noisy_thread():
    while True:
        time.sleep(3)
        sys.stdout.flush()




# create a new player and send to server
def initializeUser(timeOfConnection, opt_rtt = None):
    
    global myUserName
    now = time.time()
    #get users name
    userName = raw_input("Please enter your user name:\n")
    myUserName = userName
    # create a Player with the username
    player1 = Player(userName)
    print'Welcome, ' + userName + '!'


    # calculate the rtt
    if opt_rtt is None or opt_rtt == 0:
        rtt = now- float(timeOfConnection)
        if rtt < 0 :
            rtt = abs(rtt)
    else:
        rtt = opt_rtt


    player1.rtt = rtt


    # sending the new player info to the server
    bufferToSend = createBuffer(1, player1.name, "Server", len(str(rtt)), rtt)
    s.send(bufferToSend)
    return player1




# get user input and send input to server 
def playersMove(player1, userInput):


    #get a valid key input from the user 
    userInput = userInput.lower()
    if any(userInput in s for s in validInput):
        # check to see if the inputted move is valid depending on where the player is 
        if player1.yPos == 0 and userInput == "u":
            print("u is an invalid move because you cant move off the game board")
        elif player1.yPos == 9 and userInput == "d":
            print("d is an invalid move because you cant move off the game board")
        elif player1.xPos == 0 and userInput == "l":
            print("l is an invalid move because you cant move off the game board")
        elif player1.xPos == 9 and userInput == "r":
            print("r is an invalid move because you cant move off the game board")
        else :
            bufferToSend = createBuffer(5, player1.name, "Server", 1, userInput)
            print "sleeping for " + str(my_rtt)
            time.sleep(float(my_rtt))
            s.send(bufferToSend)
            return
            
    else:
        print("Sorry, your input is invalid")




# Convert dotted IPv4 address to integer
def from_string(s):
  return reduce(lambda a,b: a<<8 | b, map(int, s.split(".")))




# create a buffer to send to the user with the given data
def createBuffer(msgType, player1_name, msgDst, msgLen, msgData):   
    
    tupToSend =  ResponseMessage(type = msgType, source = player1_name, dest = msgDst, len = msgLen, data = msgData)

    bufferToSend = ""
    for item in tupToSend:
        bufferToSend += str(item) + "|" 


    return bufferToSend




# takes in a string of data and returns a ResponseMessage tuple 
def getResponseMsg(data):
    global partialReadBuffer
    # parsing the data
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




# clears the board by putting a "." if itsn ot an avatar
def clear_board_for_shooting():
    for i in range(10):
        for j in range(10):
                if board[i][j] not in avatars:
                    board[i][j] = "."




# clears the board if the character isnt a bullet ("@")
def clear_board_for_moving():
    for i in range(10):
        for j in range(10):
            if board[i][j] !='@':
                 board[i][j] = "."






def clear_last_row():
    for i in range(10):
        if board[i][9] not in avatars:
            board[i][9] = '.'




# called when server sends error message 3, meaning the current username is unavilable 
def userName_taken(player):
    global myUserName
    newUserName = raw_input("That username is taken, please enter a different one: ")
    newUserName = newUserName.lower()
    player.name = newUserName
    myUserName = newUserName

    bufferToSend = createBuffer(1, player.name, "Server", len(str(player.rtt)), player.rtt)
    s.send(bufferToSend)






# notifies the user that they died and sends a message to the server so it removes
# the user from its database
def handlePlayerDead(newPlayer):
    print "Sorry you died!"


    #send message to server so it can quit the player
    bufferWindow = createBuffer(5, newPlayer.name, "Server", 0, "")
    s.send(bufferWindow)
    printBoard()
    print "Thanks for playing!"
    sys.exit(0)




# sends the given message to the peer that was provided
def transferMessage(resMessage, peerToSend):


    if resMessage.source == peerToSend:
        return


    # send the given message to the specified peer
    bufferToSend = createBuffer(18, resMessage.source, peerToSend, len(resMessage.data), resMessage.data)
    
    if peerToSend not in list_of_clients:
        return
    # before every message is sent, must send a dummy message 
    dummyMessageToSend = createBuffer(20, newPlayer.name,peerToSend, str(resMessage.data), resMessage.data)
    try:
        p_sockfd.send(dummyMessageToSend)
        time.sleep(0.2)
        # sending the real message 
        p_sockfd.send(bufferToSend)
    except:
        # if the message is for a new peer that hasnt been added yet
        newPeerSocket = peerToIpPortInfo[peerToSend]
        p_sockfd = createASocket(newPeerSocket)
        try:
            # send the message to the new peer
            p_sockfd.send(bufferToSend)
            list_of_clients[peerToSend] = p_sockfd 
        except:
            # if the client just quit the game
            print peerToSend + "doesn't seem to be available to chat"
            del list_of_clients[peerToSend]




# create a socket for the specified peer and connect to it 
def createASocket(peerToChat):


    p2p_chat = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # getting the peers IP and port 
    ip = peerToChat["ip"]
    port = peerToChat["port"]
    try :
        p2p_chat.connect((ip, int(port)))
    except :
        print 'Unable to connect'


    # now that the peer is connected, add it to the list of clients
    name = peerToChat["name"]
    list_of_clients[name] = p2p_chat
    return p2p_chat




# takes in the response message and preforms the specified functionality 
# based on the response type 
def analyzeResponse(resMessage, socket_list):
    global newPlayer
    global myHealth
    global peerToIpPortInfo


    # calculating the rtt of the player
    if resMessage.type == '0':
        newPlayer = initializeUser(resMessage.data, my_rtt)
        return newPlayer


    # player has been successfully added to servers data base
    # server sends back the list of connected clients
    if resMessage.type == '2':
        # parsing the client dictionary
        playersDict = json.loads(resMessage.data)
        clear_board_for_moving()


        for username, player in playersDict.items():
            playerDict = json.loads(player)
            if username == myUserName:
                # creating a player with the username that was approved by the server
                newPlayer = Player(username,playerDict)

            x = playerDict["xPos"]
            y = playerDict["yPos"]
            myAvatar = str(playerDict["avatar"])
            # placing the player's avatar on the board
            board[y][x] = myAvatar  


    # an error occured because the provided user name is taken
    elif resMessage.type == '3':
        userName_taken(newPlayer)


    # server sends updated coordinates of the bullet 
    elif resMessage.type == '9':


        clear_board_for_shooting()
        coordinatesDict = json.loads(resMessage.data)
        # getting the updated coords of the bullet
        x = coordinatesDict["xPos"]
        y = coordinatesDict["yPos"]
        board[y][x] = "@"


    elif resMessage.type == '10':
        print "10"
        print resMessage


    # remove the bullet from the board at the coords provided by the server
    elif resMessage.type == '11':
        shooting_pos = json.loads(resMessage.data)
        x = shooting_pos["xPos"]
        y = shooting_pos["yPos"]


        board[y][x] = "."
        printBoard()
 
    # server notifies client that someone has been shot 
    elif resMessage.type == '12':
        # loading the info about the shooting
        shooting_info = json.loads(resMessage.data)
        x = shooting_info["xPos"]
        y = shooting_info["yPos"]
        victim_avatar = str(shooting_info["avatar"])


        byTrail = shooting_info["byTrail"]
        # 
        if byTrail != None:
            if x < 9:
                board[y][x + 1] = '.' 
                printBoard()
        time.sleep(1)


        shooter = shooting_info["shooter"] 
        victim = shooting_info["victim"]
        board[y][x] = victim_avatar


        # if the victim of the shot is the current client
        if victim == myUserName:
            myHealth -= 1
            print "You have been shot by " + shooter
            # if the player has no more health points, delete them from game
            if myHealth == 0:
                board[y][x] = "."
                thread.start_new_thread(noisy_thread, ())
                handlePlayerDead(newPlayer)
        else:
            # notify the client who has been shot by whom
            print shooter + " shot " + victim



    # a new player is available to chat so we need to add them to our lists
    elif resMessage.type == '15':
        peerPlayerDict = json.loads(resMessage.data)
        peerName = peerPlayerDict["name"]
        # create a new connection with the peer
        new_sockfd = createASocket(peerPlayerDict)
        # add the peers info
        peerToIpPortInfo[peerName] = peerPlayerDict
        # add the peers socket
        socket_list.append(new_sockfd)



    # print out the chat message from the source
    elif resMessage.type == '16':
        print "-->"+ resMessage.source + ":" + resMessage.data
      
    #s sends to c a list of the connected peers
    elif resMessage.type == '17':
        peerToIpPortInfo = json.loads(resMessage.data)
        for name ,peer in peerToIpPortInfo.items():
            new_sockfd = createASocket(peer)
            socket_list.append(new_sockfd)




    # the client is sending a group message
    elif resMessage.type == '18':
        groupInfo = json.loads(resMessage.data)
        groupName = groupInfo["groupName"] 
        peerToSend = findThePeerToSend(newPlayer, groupInfo["groupChat"], groupName)
        
        if groupName not in groupChats:
            print "You have been added to the following groupChat : " + groupName
        
        # if the message is not intencted for the current client, then transfer 
        # the message
        if peerToSend is not resMessage.source:
            transferMessage(resMessage, peerToSend)
        
        # if a player isnt in the given group chat
        if groupName in groupChats:
            if listNotTheSame(groupChats[groupName],groupInfo["groupChat"]):
                print "Someone has left from the groupChat"
        
        groupChats[groupName] = groupInfo["groupChat"]
        # print out the group mesasge
        print "---" + groupName + "---"
        print "-->" + resMessage.source + ":" + groupInfo["chat"]


   
    # the client is trying to chat with a peer that recently quit
    elif resMessage.type == '19':
        peerQuitting = resMessage.source
        print peerQuitting + " is no longer available!"
        # remove the player that quit from the list of clients
        if peerQuitting in list_of_clients:
            removeFromGroupChats(peerQuitting)
            del list_of_clients[peerQuitting] 
    
    else:
        print "Error in analyzeResponse"


    return newPlayer


# checks if the given lists are equal
def listNotTheSame(list1, list2):
    if len(list1) != len(list2):
        return True
    else:
        return False    




# remove the given peer from the group chats
def removeFromGroupChats(peerQuitting):
    for groupName, groupChat in groupChats.items():
        if peerQuitting in groupChat:
            groupChat.remove(peerQuitting)




# send server the starting coords of the bullet
def playerShoot(newPlayer):


    bulletCoords = {'xPos': newPlayer.xPos, 'yPos': newPlayer.yPos}
    # parse the coords as a string
    bullet_as_string = json.dumps(bulletCoords)
    bufferToSend = createBuffer(6, newPlayer.name, "Server", len(bullet_as_string), bullet_as_string)
    print "sleeping for " + str(my_rtt)
    time.sleep(float(my_rtt))
    s.send(bufferToSend)




# prints the board and necessary player info
def printBoard():
    global myUserName
    print "Health: " + str(myHealth)
    print  "Username: " + myUserName


    print"Here is the current view of the game board:"
    for i in board:
        print i




# create initial connection with server to calculate rtt
def createConnection():
    time_now = time.time()
    bufferToSend = createBuffer(0, "", "Server", len(str(time)), str(time_now))
    s.send(bufferToSend)


# notify server that a player has quit and send server their coords
def playerQuit(newPlayer):
    
    
    bulletCoords = {'xPos': newPlayer.xPos, 'yPos': newPlayer.yPos}
    bullet_as_string = json.dumps(bulletCoords)
    
    bufferToSend = createBuffer(10, newPlayer.name, "Server", len(bullet_as_string), bullet_as_string)
    s.send(bufferToSend)
    # notify peers that the player quit
    bufferToSend2 = createBuffer(19, newPlayer.name, "peer", 0, "")

    # notify all players that the player has quit
    for name, scd in list_of_clients.items():
        print ("Player is quitting, close the connection with other players")
        sendToPeer(scd, name, bufferToSend2)


    print "Thanks for playing " + (newPlayer.name) + "!"
    sys.exit(0)




# print out the available clients to chat with (if applicable)
def sendListOfPlayers(newPlayer):
    P2C = {}
    if not list_of_clients:
        print "There are no clients to chat with, tell your friends to join!"
        return False
    else:
        print "The following players are available to chat :"
        for playerName, p2p_chat in list_of_clients.items():
            if playerName != myUserName:
                print playerName
    return True 




# print out the available group chats (if applicable)
def joinExistingGroupChat(newPlayer):
    groupChat = []
    if groupChats:
        print "The following group chats are available:"
        for gc_name, g_chat in groupChats.items():
            print gc_name + "->" +str(g_chat)
    else: 
        print "Looks like you dont have any existing group chats"
        return 

    groupName = raw_input("Select the group you want to join (or enter q to quit)")
    print groupName

    while not groupName in groupChats.keys():
        if groupName == 'q':
            # player doesnt want to send chat message
            return 
        groupName = raw_input("Please chose an existing group chat: ")

    return groupName




# create a new group chat with the specified name and adds the peers that 
# the user wants to chat with (if they exist)
def createNewGroupChat(newPlayer):
    groupChat = []

    groupName = raw_input("Pick the name of your group")
    print "The following players are available:"
    for playerName, p2p_chat in list_of_clients.items():
        if playerName != myUserName:
            print playerName


    peersToChat = raw_input("Select players you would like to Chat with (or enter q to quit chat): ")
    groupChatList = peersToChat.split(" ")
    groupInfo = {}
    if len(groupChatList) == 0:
        return
    if peersToChat == 'q':
            # player doesnt want to send chat message
            return
    # add the users name to the group chat
    groupChat.append(newPlayer.name)

    # go through all of the peers the user wanted to chat with and make sure they exist
    for peer in groupChatList:
        if peer in list_of_clients.keys():
            # if the peer is available to chat, add them
            groupChat.append(peer)
        else:
            print peer +  " is not available to chat"
            return
    groupChats[groupName] = groupChat
    return groupName




# if a client wants to group message, check if they want to create a new one
# or join an existing one
def sendListOfPlayersForGroupMessage(newPlayer):


    groupChat = []
    groupInfo = {}

    # if no peers are available to chat
    if not list_of_clients:
        print "Looks like no one is available to chat!"
        return False


    answer = raw_input("Would you like to join an existing group chat or create a new one? (o/n)?")
    if answer == 'o':
        # check to see if the given group chat exists
        groupName = joinExistingGroupChat(newPlayer)
        if not groupName:
            return
    else:
        # create a new group chat
        groupName = createNewGroupChat(newPlayer)


    if groupName:
        if len(groupName) == 1:
            return
        # find the peer to send the message to
        peerToChat = findThePeerToSend(newPlayer, groupChats[groupName], groupName)
        groupInfo["groupName"] = groupName
        groupInfo["peerToSend"] = peerToChat
    else:
        return


    return groupInfo    
   


# a player is available to chat--notify the server so it can notify all players
def joinChat(newPlayer):
    bufferToSend = createBuffer(14, newPlayer.name, "Server", len(str(binding_port)), binding_port)
    
    s.send(bufferToSend)




# send the group message to the specified peer 
def sendGroupChatMessage(newPlayer, groupChatInfo):
    global peerToIpPortInfo
    groupName = groupChatInfo["groupName"]
    chatMessage = raw_input("What do you want to say?")


    peerToSend = groupChatInfo["peerToSend"]
    # creating the message to send to the peer
    messageToSend = {}
    messageToSend["chat"] = chatMessage
    messageToSend["groupChat"] = groupChats[groupName]
    messageToSend["groupName"] = groupName
    messageToSend["peerSender"] = newPlayer.name
    messageToSendAsString = json.dumps(messageToSend)


    dummyMessageToSend = createBuffer(20, newPlayer.name,peerToSend, str(messageToSend), messageToSend)
    # sending the message to the peer
    bufferToSend = createBuffer(18, newPlayer.name, peerToSend, len(messageToSendAsString), messageToSendAsString)
    p_sockfd = list_of_clients[peerToSend]
   
    # first send the dummy message, then the real message
    try:
        p_sockfd.send(dummyMessageToSend)
        sleep(0.2)
        p_sockfd.send(bufferToSend)
    except:
        # a new peer is being added
        newPeerSocket = peerToIpPortInfo[peerToSend]
        p_sockfd = createASocket(newPeerSocket)
        list_of_clients[peerToSend] = p_sockfd
        try:
            p_sockfd.send(bufferToSend)
        except:
            # the peer to message is no longer available to chat
            del list_of_clients[peerToSend]
            groupChats[groupName].remove(peerToSend)
            if groupChats:
                print peerToSend + "has left the chat"
                new_peer = findThePeerToSend(newPlayer, groupChats[groupName], groupName)
                messageToSend["groupChat"] = groupChats[groupName]
                messageToSendAsString = json.dumps(messageToSend)
                bufferToSend = createBuffer(18, newPlayer.name, peerToSend, len(messageToSendAsString), messageToSendAsString)
                sendToPeer(p_sockfd, new_peer, bufferToSend, dummyMessageToSend)
            else:
                "No one is available in that groupChat"




# sends the given message to the peer provided
def sendToPeer(p_sockfd, peerToSend, messageToSend, dummyMessageToSend = None):
    try:
        if dummyMessageToSend is not None:
            p_sockfd.send(dummyMessageToSend)
            sleep(0.2)
        p_sockfd.send(messageToSend)
    except:
        # get the peers info
        newPeerSocket = peerToIpPortInfo[peerToSend]
        p_sockfd = createASocket(newPeerSocket)
        list_of_clients[peerToSend] = p_sockfd
        try:
            p_sockfd.send(messageToSend)
        except:
            print peerToSend + "doesn't seem to be available to chat"
            del list_of_clients[peerToSend]




# used to get the info about the given socket
def printInfoAboutSocket(socket):
    print "Socket is "
    print socket
    if socket is not sys.stdin:
        try:
            ip = socket.getpeername()
        except:
            print "socket not connected"
            return False
        print "ip is " + str(ip)
    else:
        print "getting traffic from stdin"
    
    print "socket is " + str(socket)
    return True






def sendChatMessage(newPlayer, peerToChat, messageToSend):
    global peerToIpPortInfo


    bufferToSend = createBuffer(16, newPlayer.name, peerToChat["name"], len(messageToSend), messageToSend)
    dummyMessageToSend = createBuffer(20, newPlayer.name,peerToChat["name"], str(messageToSend), messageToSend)
    p_sockfd = peerToChat["sockfd"]
    
    try:
        # first send the dummy message, then the real message
        p_sockfd.send(dummyMessageToSend)
        sleep(0.2)
        p_sockfd.send(bufferToSend)
    except:
        # if the peer is new, create a socket and add them to the list
        peerName = peerToChat["name"]   
        newPeerSocket = peerToIpPortInfo[peerName]
        p_sockfd = createASocket(newPeerSocket)
        list_of_clients[peerName] = p_sockfd
        try:
            p_sockfd.send(bufferToSend)
        except:
            # if the peer is unavailable to char
            print peerName + " doesn't seem to be available to chat"
            del list_of_clients[peerName]
            removeFromGroupChats(peerName)
    # output the message that the user wishes to send
    print "--> " + newPlayer.name + ": " + messageToSend




# find the peer to send the chat to
def findThePeerToSend(newPlayer, groupChat, groupName):
    sizeOfList = len(groupChat) 

    index = groupChat.index(newPlayer.name)

    if index < sizeOfList - 1:
        peerToSend = groupChat[index + 1]
    else:
        peerToSend = groupChat[0]

    return peerToSend


    
newPlayer = ""
myHealth = 5
global partialReadBuffer
partialReadBuffer = ""
createConnection()


p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
p2p_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)




try:
       p2p_socket.bind(('comp112-01', binding_port))
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
        # Get the list sockets which are readable
    try:
        read_sockets, write_sockets, error_sockets = select.select(inputs , outputs, inputs, 2)
    except select.error as e:
        if e[0] == 4:
            continue
        else:
            raise


    for sock in read_sockets:
        
        if sock is p2p_socket:
            connection, client_address = sock.accept()
            connection.setblocking(0)
            inputs.append(connection)
            message_queues[connection] = Queue.Queue()


        #incoming message from  server
        elif sock == s:
            data = sock.recv(1054)
            if not data :
                print '\nServer disconnected'
                serverUp = False
                if sock in outputs:
                    outputs.remove(sock)
                inputs.remove(sock)
            else :
                # dealing with partial Reads
                correct_data = partialReadBuffer + data
                newMsg = getResponseMsg(correct_data)
                newPlayer = analyzeResponse(newMsg ,socket_list)
                if len(partialReadBuffer) != 0:
                    new_msg = getResponseMsg(partialReadBuffer)
                    analyzeResponse(new_msg, socket_list)
                printBoard()
                if pickAPeerToChatWithMode:
                    if sendListOfPlayers(newPlayer) != True:
                        pickAPeerToChatWithMode = False
                        chatMode = False
                elif readyToChat:
                    print "Do you stil want to chat with " + temp_peerToChat + "? \n Press e if you don't, otherwise enter your message"
        
        # the player has inputted something
        elif sock is sys.stdin:
            c = sys.stdin.readline()
            c = c.strip('\n')
            c = c.lower()
            if chatMode and c is not 'e':
                P2C = {}
                if pickAPeerToChatWithMode:
                    temp_peerToChat = c
                    # see if the peer exists
                    if temp_peerToChat not in list_of_clients:
                        if temp_peerToChat == 'q':
                            pickAPeerToChatWithMode = False
                            chatMode = False
                            break;
                        print("Please chose an existing player: ")
                    else:
                        readyToChat = True
                        pickAPeerToChatWithMode = False
                        print("What do you want to say?")


                elif readyToChat == True:
                    messageToSend = c
                    # get the socket info and the name of the peer
                    P2C["sockfd"] = list_of_clients[temp_peerToChat]
                    P2C["name"] = temp_peerToChat
                    # send the chat message
                    sendChatMessage(newPlayer, P2C, messageToSend)
                    readyToChat = False
                    chatMode = False
            elif c == 'e':
                if chatMode:
                    print "Leaving chat mode"
                    chatMode = False
                else:
                    print "You are not in chat mode"


            # the player is shooting
            elif c == 's':
                if serverUp:
                    playerShoot(newPlayer)
                else:
                    print "Sorry, the server is down. Try again later, but you can still use the chat feature"
            # the player has quit
            elif c == 'q':
                playerQuit(newPlayer)


            # the player is now available to chat
            elif c == 'j':
                if availableToChat == False:
                    availableToChat = True
                    joinChat(newPlayer)
                else:
                    print "You're already available to chat! No need to join again."
            
            # player wants to chat
            elif c == 'c':
                if (availableToChat):
                    inputs.remove(sys.stdin)
                    thread.start_new_thread(noisy_thread, ())
                    if sendListOfPlayers(newPlayer):
                        pickAPeerToChatWithMode = True
                        chatMode = True
                    inputs.append(sys.stdin)
                else:
                    print "Please type j to enable the chat feature" 
            # player wants to group char
            elif c == 'g':
                if (availableToChat):
                    inputs.remove(sys.stdin)
                    thread.start_new_thread(noisy_thread, ())
                    groupChatInfo = sendListOfPlayersForGroupMessage(newPlayer)
                    if groupChatInfo:
                        sendGroupChatMessage(newPlayer, groupChatInfo)
                    inputs.append(sys.stdin)
                else:
                    print "Please type j to enable the chat feature"
            else:
                if serverUp:
                    # the player is moving
                    playersMove(newPlayer, c) 
                else:
                    # the server is down so the players cant move
                    if c != '\n':
                        print "Sorry, the server is down. Try again later, but you can still use the chat feature"
            if c in validInput or (c == 'j' and chatMode == False):
                if serverUp:
                    printBoard()
            thread.start_new_thread(noisy_thread, ())
        else:
            data = sock.recv(1054)
            if not data:
                # if there is not data 
                if sock == s:
                    print '\n There was an error with the server'
                else:
                    # some one has quit, remove them from the list of clients
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
        else:
            s.send(next_msg)
    for s in error_sockets:
        socket_list.remove(s)
        if s in outputs:
            outputs.remove(s)
        s.close()
        del message_queues[s]




