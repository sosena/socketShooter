#!/usr/bin/python




import select, socket, sys, Queue
import collections
import json
import threading
from random import randint
from heapq import *




############ Message Types #################
# Type 1: new player
# Type 2 : ack + send back the dictioanry
# Type 3: error message
# Type 4 : send back board after another client moves/shoot 
# type 5 : player moving
# type 6    shooting
#type 7 : player exit
#type 8: player dies 
#type 9 : sever to client updated coordinate of bullets: 
#type 10: shooting message
#type 11 : remove bullet from screen
#type 1socket.MSG_OOB: signals to player to die




class Player:
    xPos = 0
    yPos = 0
    health = 2
    points = 0
    name = ""
    delay = 0
    port = -1




    def __init__(self, name, xPos, yPos, delay):
        self.name = name
        self.xPos = xPos
        self.yPos = yPos
        self.delay = delay






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
global shootingStop 
shootingStop = False
rttHeap = []


board = [ ["."] * SIZE_OF_BOARD for i in range(SIZE_OF_BOARD)]






def check_bounds(x, y):
    return ( x in range(0, SIZE_OF_BOARD) and y in range(0, SIZE_OF_BOARD))




# updates the position of the player and checks to see if their move is valid
def updatePosition (resMessage):
    direction = resMessage.data
    if direction in movement:
        new_x_pos = players[resMessage.source].xPos + movement[direction].x
        new_y_pos = players[resMessage.source].yPos + movement[direction].y
        if check_bounds(new_x_pos, new_y_pos) :
            if board[new_x_pos][new_y_pos] != '.':
                print board[new_x_pos][new_y_pos]
            else:
                board[new_x_pos - movement[direction].x][new_y_pos - movement[direction].y] = '.'
                board[new_x_pos][new_y_pos] = 'X'
                players[resMessage.source].xPos += movement[direction].x
                players[resMessage.source].yPos += movement[direction].y
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






# gets the positon of the player and gets rid of the X
# notifies players that a player has been killed
def sendPlayerDies(pos, resMessage):
    player = findPlayer(pos)
    shooting_info = {}
    shooting_info["xPos"] = pos["xPos"]
    shooting_info["yPos"] = pos["yPos"]
    shooting_info["shooter"] = resMessage.source
    shooting_info["victim"] = player.name


    players[player.name].health -= 1


    # sending the info as a string dictionary
    shooting_info_string = json.dumps(shooting_info)
    bufferToSendToShooter = createBufferMessage(resMessage.source, shooting_info_string, 12 )
    bufferToSendToVictim = createBufferMessage(player.name, shooting_info_string, 12 )  
    bufferToSend = createBufferMessage(resMessage.source, "Player " +  resMessage.source + "shot player "+ player.name, 10)


    
    victim_sockfd = players_to_sockets[player.name]
    shooter_sockfd = players_to_sockets[resMessage.source]
    victim_sockfd.send(bufferToSendToVictim )
    shooter_sockfd.send(bufferToSendToShooter)
    
    if players[player.name].health == 0:
        removePlayerFromGame(player)


    for sockfd in message_queues:
        if sockfd != shooter_sockfd and sockfd != victim_sockfd:
            sockfd.send(bufferToSend )






# removes a player from the board
def removePlayerFromGame(player):
        #del message_queues[players_to_sockets[player.name]]
        removeDelay(player)
        del players_to_sockets[player.name]
        del players[player.name]
        x = player.xPos
        y = player.yPos
        board[x][y] = '.'


# uses a timer to send off the bullet by increasing its position by 1 every second 
def setOffShooting(start_pos, resMessage, sockfd):
    global shootingStop
    
    t = threading.Timer(1, setOffShooting, [start_pos, resMessage, sockfd])
    t.start()
    
    if start_pos["xPos"] >= SIZE_OF_BOARD - 1 :
        t.cancel()
        coorAsString = json.dumps(start_pos)
        bufferToSend = createBufferMessage(resMessage.source, coorAsString, 11)
        for sockfd in message_queues:
            sockfd.sendall(bufferToSend )
        return 
    start_pos["xPos"] += 1


    coorAsString = json.dumps(start_pos)
    bufferToSend = createBufferMessage(resMessage.source, coorAsString, 9)
    for sockfd in message_queues:


        sockfd.send(bufferToSend )
    
    if board[start_pos["xPos"]][start_pos["yPos"]] == 'X':
        t.cancel()
        return sendPlayerDies(start_pos, resMessage)




def startShooting(resMessage, sockfd):
    global shootingStop
    new_coor = {}
    coordinate =  json.loads(resMessage.data)
    new_coor["xPos"] = coordinate["xPos"]
    new_coor["yPos"] = coordinate["yPos"] 
    coorAsString = ""
    t = threading.Timer(1, setOffShooting, [new_coor, resMessage, sockfd])


    t.start()
    


def announceToAllPlayers(resMessage, sockfd):
    peerConnectionInfo = {}
    peerConnectionInfo["name"] = resMessage.source
    peerConnectionInfo["port"] = resMessage.data
    ip = sockfd.getpeername()[0]
    peerConnectionInfo["ip"] = str(ip)


    peerConnectionAsString = json.dumps(peerConnectionInfo)
    bufferToSend = createBufferMessage(resMessage.source, peerConnectionAsString, 15)


    players[resMessage.source].port = resMessage.data
    connectedPeers[resMessage.source] = peerConnectionInfo


    for peer_sockfd in message_queues:
        if peer_sockfd != sockfd:
            peer_sockfd.send(bufferToSend )




def sendConnectedPeers(resMessage, sockfd):
    connectedPeersAsString = json.dumps(connectedPeers)
    bufferToSend = createBufferMessage(resMessage.source, connectedPeersAsString, 17)
    sockfd.send(bufferToSend)






# gets the message from the client and decodes it to determine what to do
def analyzeResponse(resMessage, sockfd):


    if resMessage.type == '0':
        bufferToSend = createBufferMessage(resMessage.source, resMessage.data, 0)
        sockfd.send(bufferToSend)
        return True


    if resMessage.source not in players and resMessage.type != '1':
        return False


    if resMessage.type == '1':
        # create a player with the given name
        if resMessage.source in players:
            sendErrorMessage(sockfd, resMessage)
        else:
            x_pos = randint(0,SIZE_OF_BOARD -1)
            y_pos = randint(0,SIZE_OF_BOARD - 1)
            # first calculate the delay of the player
            delay = assessDelay(float(resMessage.data), resMessage.source)
            player = Player(resMessage.source, x_pos, y_pos, delay )
            players[resMessage.source] = player
            players_to_sockets[resMessage.source] = sockfd
            board[x_pos][y_pos] = 'X'
            sendPlayerMapView(resMessage)


    if resMessage.type == '5':
        # a player is moving
        if resMessage.source in players:
            delay = players[resMessage.source].delay
            t = threading.Timer(delay, updatePosition, [resMessage])
            t.start()


    if resMessage.type == '6':
        # a player is shooting
        delay = players[resMessage.source].delay
        t = threading.Timer(delay, startShooting, [resMessage, sockfd])
        t.start()




    if resMessage.type == '10':
        player_coord = {}
        coordinate =  json.loads(resMessage.data)
        player_coord["xPos"] = coordinate["xPos"]
        player_coord["yPos"] = coordinate["yPos"] 
        # the client has alerted the server that they are quitting
        player = findPlayer(player_coord)
        removePlayerFromGame(player)
        sendPlayerMapView(resMessage)
        return False
    if resMessage.type == '14':
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






def createMessage(data):
    dataAsList = data.split("|",5)
    correctList = dataAsList[:5]
    responseMessage = ResponseMessage._make(correctList)


    return responseMessage






def main():
    port = input("Enter port number ")


    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setblocking(0)
    server.bind(('localhost', port))
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
                                # ie a player has quit
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


