# Comp 112 Final Project----client/server shooting game with chat/group char capabilities
# Written by: Sosena Bekele and Becky Cutler
# 12/14/17


import select, socket, sys, Queue
import collections
import json
import threading
from random import randint
from heapq import *


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
    delay = 0
    port = -1
    avatar = ""


    def __init__(self, name, xPos, yPos, delay, avatar):
        self.name = name
        self.xPos = xPos
        self.yPos = yPos
        self.delay = delay
        self.avatar = avatar


# Global Variables
Coordinate = collections.namedtuple('Coordinate', 'x y')
movement = {}
players_to_sockets = {}
connectedPeers = {}
ResponseMessage = collections.namedtuple('ResponseMessage', 'type source dest len data')
players = {}
SIZE_OF_BOARD = 10
message_queues = {}
movement['u'] = Coordinate(x= 0 , y = -1)
movement['d'] = Coordinate(x= 0 , y = 1)
movement['l'] = Coordinate(x= -1 , y = 0)
movement['r'] = Coordinate(x= 1 , y = 0)
players_to_avatars = {}
avatars = Queue.Queue()
global shootingStop 
shootingStop = False
rttHeap = []



board = [ ["."] * SIZE_OF_BOARD for i in range(SIZE_OF_BOARD)]
avatars.put('X')
avatars.put('O')
avatars.put('*')



def check_bounds(x, y):
    return (x in range(0, SIZE_OF_BOARD) and y in range(0, SIZE_OF_BOARD))



# updates the position of the player and checks to see if their move is valid
def updatePosition (resMessage):
    direction = resMessage.data
    if direction in movement:
        # if the direction is valid, calculate the new position
        new_x_pos = players[resMessage.source].xPos + movement[direction].x
        new_y_pos = players[resMessage.source].yPos + movement[direction].y
        if check_bounds(new_x_pos, new_y_pos) :
            if board[new_x_pos][new_y_pos] != '.':
                print board[new_x_pos][new_y_pos]
            else:
                board[new_x_pos - movement[direction].x][new_y_pos - movement[direction].y] = '.'
                # update the board with the player's avatar
                board[new_x_pos][new_y_pos] = players_to_avatars[resMessage.source]
                players[resMessage.source].xPos += movement[direction].x
                players[resMessage.source].yPos += movement[direction].y
        # send the updated board
        sendPlayerMapView(resMessage)
    


# creates the buffer message to be sent
def createBufferMessage(source, data, type_of_mess):
    message = ResponseMessage(type = type_of_mess, source = "server",  dest = source,
                             len = len(data), data =  data)
    bufferToSend = ""
    for item in message:
        bufferToSend += str(item) + "|"


    return bufferToSend



# sends error message that the user name already exists
def sendErrorMessage(sockfd, resMessage):
    bufferToSend = createBufferMessage(resMessage.source, "Username is already taken", 3)
    sockfd.send(bufferToSend )



# sends the current view of the board
def sendPlayerMapView( resMessage):
    serializablePlayers = {}
    players_as_string = ""

    # formatting the message 
    for username, player in players.items():
        serializablePlayers[username] = json.dumps(player.__dict__)
    
    players_as_string = json.dumps(serializablePlayers)


    bufferToSend = createBufferMessage(resMessage.source, players_as_string, 2)
    for sockfd in message_queues:
        sockfd.send(bufferToSend)   


# finds the player from the given position
def findPlayer(pos):
    for username, player in players.items():
        if player.xPos == pos["xPos"]:
            return player




# gets the positon of the player and gets rid of their avatar
# notifies players that a player has been killed
def sendPlayerDies(pos, resMessage, byTrail = None):
    player = findPlayer(pos)
    shooting_info = {}
    # getting all of the shooting info
    shooting_info["xPos"] = pos["xPos"]
    shooting_info["yPos"] = pos["yPos"]
    shooting_info["shooter"] = resMessage.source
    shooting_info["victim"] = player.name
    shooting_info["avatar"] = players_to_avatars[player.name]
    shooting_info["byTrail"] = byTrail 


    players[player.name].health -= 1


    # sending the info as a string dictionary
    shooting_info_string = json.dumps(shooting_info)
    bufferToSendToShooter = createBufferMessage(resMessage.source, shooting_info_string, 12 )
    bufferToSendToVictim = createBufferMessage(player.name, shooting_info_string, 12 )  
    bufferToSend = createBufferMessage(resMessage.source, "Player " +  resMessage.source + "shot player "+ player.name, 10)


    # sending the different messages to the shooter and the victim
    victim_sockfd = players_to_sockets[player.name]
    shooter_sockfd = players_to_sockets[resMessage.source]
    victim_sockfd.send(bufferToSendToVictim )
    shooter_sockfd.send(bufferToSendToShooter)
    
    # if the player has no more health points, remove them 
    if players[player.name].health == 0:
        removePlayerFromGame(player)

    # notify the players that someone has been shot
    for sockfd in message_queues:
        if sockfd != shooter_sockfd and sockfd != victim_sockfd:
            sockfd.send(bufferToSend)



# removes a player from the game
def removePlayerFromGame(player):
        # delete the player and remove their delay from the heap
        removeDelay(player)
        del players_to_sockets[player.name]
        del players[player.name]
        x = player.xPos
        y = player.yPos
        board[x][y] = '.'



# uses a timer to send off the bullet by increasing its position by 1 every second 
def setOffShooting(start_pos, resMessage, sockfd):
    global shootingStop
    trail = {}
    t = threading.Timer(1, setOffShooting, [start_pos, resMessage, sockfd])
    t.start()
    
    # if the bullet has gone out of range
    if start_pos["xPos"] >= SIZE_OF_BOARD - 1 :
        t.cancel()
        coorAsString = json.dumps(start_pos)
        bufferToSend = createBufferMessage(resMessage.source, coorAsString, 11)
        for sockfd in message_queues:
            sockfd.sendall(bufferToSend )
        return 
    start_pos["xPos"] += 1


    coorAsString = json.dumps(start_pos)
    # send the clients the updated bullet coords
    bufferToSend = createBufferMessage(resMessage.source, coorAsString, 9)
    for sockfd in message_queues:
        sockfd.send(bufferToSend )


    trail["xPos"] = start_pos["xPos"] - 1
    trail["yPos"] = start_pos["yPos"]
    # if the bullet has reached a player
    if board[start_pos["xPos"]][start_pos["yPos"]] != '.':
        t.cancel()
        return sendPlayerDies(start_pos, resMessage)
    elif board[trail["xPos"]][trail["yPos"]] != '.' and trail["xPos"] != players[resMessage.source].xPos:
        t.cancel()
        return sendPlayerDies(trail, resMessage, True)




# uses a thread to shoot the bullet every second
def startShooting(resMessage, sockfd):
    global shootingStop
    new_coor = {}
    # getting the starting coords of the bulllet
    coordinate =  json.loads(resMessage.data)
    new_coor["xPos"] = coordinate["xPos"]
    new_coor["yPos"] = coordinate["yPos"] 
    coorAsString = ""
    t = threading.Timer(1, setOffShooting, [new_coor, resMessage, sockfd])

    t.start()
    


# announce to all players that a new peer is available to chat
def announceToAllPlayers(resMessage, sockfd):
    peerConnectionInfo = {}
    # getting the peer info
    peerConnectionInfo["name"] = resMessage.source
    peerConnectionInfo["port"] = resMessage.data
    ip = sockfd.getpeername()[0]
    peerConnectionInfo["ip"] = str(ip)

    peerConnectionAsString = json.dumps(peerConnectionInfo)
    bufferToSend = createBufferMessage(resMessage.source, peerConnectionAsString, 15)

    players[resMessage.source].port = resMessage.data
    connectedPeers[resMessage.source] = peerConnectionInfo


    # sending the messages to all of the peers
    for peer_sockfd in message_queues:
        if peer_sockfd != sockfd:
            peer_sockfd.send(bufferToSend)



# sends a list of the connected peers to the given client 
def sendConnectedPeers(resMessage, sockfd):
    connectedPeersAsString = json.dumps(connectedPeers)
    bufferToSend = createBufferMessage(resMessage.source, connectedPeersAsString, 17)
    sockfd.send(bufferToSend)



# getting an avatar for a player
def getAvailableAvatar():
    print "getting avatar ..."
    avatar = avatars.get_nowait()
    print "avatar is " + avatar
    avatars.put(avatar)
    return avatar



# gets the message from the client and decodes it to determine what to do
def analyzeResponse(resMessage, sockfd):


    # used to calculate the rtt of the client
    if resMessage.type == '0':
        bufferToSend = createBufferMessage(resMessage.source, resMessage.data, 0)
        sockfd.send(bufferToSend)
        return True


    # if a username is valid, create a new player
    if resMessage.source not in players and resMessage.type != '1':
        return False


    if resMessage.type == '1':
        # create a player with the given name
        if resMessage.source in players:
            sendErrorMessage(sockfd, resMessage)
        else:
            x_pos = randint(0,SIZE_OF_BOARD -1)
            y_pos = randint(0,SIZE_OF_BOARD - 1)
            while board[x_pos][y_pos] != '.':
                x_pos = randint(0,SIZE_OF_BOARD -1)
                y_pos = randint(0,SIZE_OF_BOARD - 1)
            # first calculate the delay of the player
            delay = assessDelay(float(resMessage.data), resMessage.source)
            print "player " + resMessage.source + "delay is " + str(delay)
            avatar = getAvailableAvatar()
            print " After avatar is " + str(avatar)
            player = Player(resMessage.source, x_pos, y_pos, delay , avatar)
            players[resMessage.source] = player
            players_to_sockets[resMessage.source] = sockfd
            board[x_pos][y_pos] = avatar
            players_to_avatars[resMessage.source] = avatar
            sendPlayerMapView(resMessage)


    # a player is moving so we must update their position
    if resMessage.type == '5':
        # a player is moving
        if resMessage.source in players:
            delay = players[resMessage.source].delay
            print "player " + resMessage.source + "delay is " + str(delay)
            t = threading.Timer(delay, updatePosition, [resMessage])
            t.start()


    if resMessage.type == '6':
        # a player is shooting
        delay = players[resMessage.source].delay
        print "player " + resMessage.source + "delay is " + str(delay)
        t = threading.Timer(delay, startShooting, [resMessage, sockfd])
        t.start()


    # a client is quitting
    if resMessage.type == '10':
        player_coord = {}
        coordinate =  json.loads(resMessage.data)
        player_coord["xPos"] = coordinate["xPos"]
        player_coord["yPos"] = coordinate["yPos"] 
        player = findPlayer(player_coord)
        # remove the player and send out the new board
        removePlayerFromGame(player)
        sendPlayerMapView(resMessage)
        print "quitting"
        return False


    # a new client is available to chat    
    if resMessage.type == '14':
        print "in type " + resMessage.type
        if len(connectedPeers) > 0:
            sendConnectedPeers(resMessage, sockfd)
        announceToAllPlayers(resMessage, sockfd)
   
    return True


# if a player is leaving, we need to remove their RTT from the heap and update the delay
# because now there will be a different slowest client
def removeDelay(player):
    # a player has left the game, so we need to check to see if they were the slowest


    if(player.delay == 0):
        # the player that left was the slowest, need to take it out of the heap and heapify
        curMaxRTT = heappop(rttHeap)
        curMaxRTT = abs(curMaxRTT)
        heapify(rttHeap)


        if not rttHeap:
            # we just popped off the last player
            return
         
        newMaxRTT = abs(rttHeap[0])
        delayDifference = curMaxRTT - newMaxRTT

        # need to subtract the delay difference from all players' delays
        recalculateDelay(delayDifference, player.name, 0)
    else:
        # the player that left wasnt the slowest so re just have to remove them from 
        # the heap
        heappop(rttHeap)
        heapify(rttHeap)



# a new player has joined so we need to see if they are the slowest player and if so, update the delays
def assessDelay(rtt,name):
    # have to mult rtt by -1 bc python only has min heaps
    negativeRtt = rtt * -1
    delay = 0
    # first check if the heap is empty 
    if not rttHeap:
        heappush(rttHeap, negativeRtt)
        return delay
    else: 
        # if its not empty, check if the rtt of the player is larger than the max in the heap
        # get the current max rtt
        prevMax = abs(rttHeap[0]) 
        # add new rtt it to the heap
        heappush(rttHeap, negativeRtt)
        heapify(rttHeap)
        if rttHeap[0] == negativeRtt:
            # the rtt we added has the slowst delay
            # recalculate everyone's delay based of off the new player's rtt 
            delayDifference = rtt - prevMax
            recalculateDelay(delayDifference, name, 1)
            # bc the new player is the slowest, the delay will be 0
            return delay


        else:
            # this rtt isnt the highest, calcualte only the new players delay 
            delay = abs(rttHeap[0] + rtt)
            return delay


# the delay has changed so we need to recalculate everyones delays 
def recalculateDelay(delayDifference, name, newClient):
    # go through the list of players and for each player, add the difference between the new delay and 
    # the old delay, dont want to do this for the current player
    for username, player in players.items():
        if player.name != name:
            if newClient == 1:
                # we are adding a delay, so add the difference
                player.delay += delayDifference
            else:
                # getting rid of a delay so subtract the difference
                player.delay -= delayDifference




# get the proper formatting for a response message
def createMessage(data):
    dataAsList = data.split("|",5)
    correctList = dataAsList[:5]
    responseMessage = ResponseMessage._make(correctList)


    return responseMessage


def main():
    port = input("Enter port number ")


    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setblocking(0)
    server.bind(('comp112-01', port))
    print "listening on port " + str(port)
    server.listen(5)
    inputs = [server]
    outputs = []
    
    while inputs:
        readable, writable, exceptional = select.select(
            inputs, outputs, inputs)
        for s in readable:
                if s is server:
                        connection, client_address = s.accept()
                        connection.setblocking(0)
                        inputs.append(connection)
                        message_queues[connection] = Queue.Queue()
                else:
                    data = s.recv(1024)
                    if data:
                        # if the server has received data, we need to analyze it
                        responseMessage = createMessage(data)
                        if analyzeResponse(responseMessage, s) == False:
                            # someone is quitting or an error occured
                            if s is outputs:
                                outputs.remove(s)
                            inputs.remove(s)
                            s.close()
                            del message_queues[s]
                        else:
                            if s not in outputs:
                                outputs.append(s)
                    else:
                        if s in outputs:
                            outputs.remove(s)
                        inputs.remove(s)
                        for name, sockfd in players_to_sockets.items():
                            if sockfd == s:
                                # ie a player has quit--remove them from the game
                                playerToDelte = players[name]
                                removeDelay(playerToDelte)
                                x = players[name].xPos
                                y = players[name].yPos
                                del players_to_sockets[name]
                                del players[name]
                                if name in connectedPeers:
                                    del connectedPeers[name]
                                board[x][y] = '.'
                        s.close()
                        del message_queues[s]

        for s in writable:
            try:
                next_msg = message_queues[s].get_nowait()
            except Queue.Empty:
                outputs.remove(s)
            else:
                s.send(next_msg)

        for s in exceptional:
            inputs.remove(s)
            if s in outputs:
                outputs.remove(s)
            s.close()
            del message_queues[s]


# call main
main()




