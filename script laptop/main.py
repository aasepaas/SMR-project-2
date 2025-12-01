from camera import DataMatrixDecoder
from camera import CameraScanner
from networkClientClass import Network_client
from lineReader import LineReader
from database import Database
import time
import sys


if __name__ == "__main__":
    ####init of all the objects from the classes
    # Choosing the correct camera
    # 1 is the external camera and 0 is laptop camera except for Jasmijns laptop
    scanner = CameraScanner(1)

    #start the socketserver so the robot can connect
    #for now the ip is localhost but change it to the ip on the same range as the robot
    socketServer = Network_client("127.0.0.1", 12344)
    socketServer.strt_socket()
    socketServer.connect_client()

    #make linereader object to get the coords of box and wallets
    boxCoordsReader = LineReader("boxCoords")
    walletCoordsReader = LineReader("walletCoords")

    #database oject #make sure the database exist check github if you dont know how to do that
    #change variables if different for your database
    db = Database("localhost", "root", "root", "secrid")

    #recv and send data variables
    recvStepBoxCoords = "boxCoords"
    recvStepWalletCoords = "walletCoords"
    recvStepStartScan = "startScan"
    sendStepBoxFound = "boxFound"

    ##########main loop
    boxID = 0
    steps = 0
    matchid = 0

    while True:
        match steps:
            ###init already happened so empty
            case 0:
                steps = 1

            ### wait for message that robot is ready and send the box pickup coords
            case 1:
                recvData = socketServer.receive_client()
                if recvData is not None and recvData == recvStepBoxCoords:
                    boxCoords = boxCoordsReader.get_next_line()
                    if boxCoords is not None:
                        socketServer.send_client(boxCoords)
                steps = 2

            #### wait for the robot to tell if he is ready to let box scan step begin
            case 2:
                recvData = socketServer.receive_client()
                if recvData is not None and recvData == recvStepStartScan:
                    scanner.run()
                    boxID = scanner.get_datamatrix_code()
                    if boxID:
                        print(boxID)
                        ###add extra error handling if it isnt an existing boxid
                        boxidreturn = db.determine_matching_id(boxID)
                        print(boxidreturn)
                        socketServer.send_client(sendStepBoxFound)
                        steps = 3
                    else:
                        print("No datamatrix code")
                        socketServer.send_client(sendStepBoxFound)
                        ###for now also step 3 but in reality it needs to be the error handling step
                        steps = 3

            ####wait for the robot to ask for the wallet coords
            case 3:
                recvData = socketServer.receive_client()
                if recvData is not None and recvData == recvStepWalletCoords:
                    walletCoords = walletCoordsReader.get_next_line()
                    if walletCoords is not None:
                        socketServer.send_client(walletCoords)
                steps = 4

            ###start the check for datamatrix again if robot asks for it
            case 4:
                recvData = socketServer.receive_client()
                if recvData is not None and recvData == recvStepStartScan:
                    scanner.run()
                    matchid = scanner.get_datamatrix_code()
                    if matchid:
                        print(matchid)
                        ###add extra error handling if it isnt an existing matchup of IDs
                        db.check_id(boxID, matchid)
                        socketServer.send_client(sendStepBoxFound)
                        steps = 5
                    else:
                        print("No datamatrix code")
                        socketServer.send_client(sendStepBoxFound)
                        ###for now also step 5 but in reality it needs to be the error handling step
                        steps = 5
            case 5:
                steps = 0

            case _:
                steps = 0
