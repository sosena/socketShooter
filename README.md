# socketShooter
 
Becky Cutler 
Sosena Bekele



README

To run the server:
	Python server.py
then enter a valid port name 

To run the client:
	Python client.py <server port> <client’s  port> <fake RTT>

Comments:
  For the fake rtt, put 0 if you want the actual RTT between you and the server
  You must be logged in on the comp112-01 server to use this application 

Test cases
  playing with multiple clients 
  a client tries to join with a port that’s already taken
  a client tries to join with a name that’s already taken
  trying to chat a player before you’ve joined
  trying to chat a player that doesn’t exist
  creating a group chat with players that don’t exist
  starting a chat when no other players are available to chat
