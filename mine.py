import requests
from fastapi import FastAPI
import fastapi
from pydantic import BaseModel
import uvicorn
import os
import signal
import logging
#import pytest

"""
By Todd Dole, Revision 1.2
Written for Hardin-Simmons CSCI-4332 Artificial Intelligence
Revision History
1.0 - API setup
1.1 - Very basic test player
1.2 - Bugs fixed and player improved, should no longer forfeit
"""

DEBUG = True
PORT = 10600
USER_NAME = "hjh2112"
# TODO - change your method of saving information from the very rudimentary method here
hand = [] # list of cards in our hand
discard = [] # list of cards organized as a stack
cannot_discard = ""

# set up the FastAPI application
app = FastAPI()

# set up the API endpoints
@app.get("/")
async def root():
    ''' Root API simply confirms API is up and running.'''
    return {"status": "Running"}

# data class used to receive data from API POST
class GameInfo(BaseModel):
    game_id: str
    opponent: str
    hand: str

@app.post("/start-2p-game/")
async def start_game(game_info: GameInfo):
    ''' Game Server calls this endpoint to inform player a new game is starting. '''
    # TODO - Your code here - replace the lines below
    global hand
    global discard
    hand = game_info.hand.split(" ")
    hand.sort()
    logging.info("2p game started, hand is "+str(hand))
    return {"status": "OK"}

# data class used to receive data from API POST
class HandInfo(BaseModel):
    hand: str

@app.post("/start-2p-hand/")
async def start_hand(hand_info: HandInfo):
    ''' Game Server calls this endpoint to inform player a new hand is starting, continuing the previous game. '''
    # TODO - Your code here
    global hand
    global discard
    discard = []
    hand = hand_info.hand.split(" ")
    hand.sort()
    logging.info("2p hand started, hand is " + str(hand))
    return {"status": "OK"}

import logging

def process_events(event_text):
    """Processes event text from various API endpoints."""
    global hand
    global discard

    if not event_text:
        return  # No events to process

    hand_updated = False  # Flag to check if sorting is needed

    for event_line in event_text.splitlines():
        words = event_line.split()
        if not words:
            continue  # Skip empty lines

        last_word = words[-1]  # The last word typically represents the card

        if USER_NAME in event_line:
            if "draws" in event_line or "takes" in event_line:
                logging.info(f"{USER_NAME} drew {last_word}")
                hand.append(last_word)
                hand_updated = True

        elif "discards" in event_line:
            logging.info(f"Adding {last_word} to discard pile")
            discard.insert(0, last_word)

        elif "takes" in event_line:
            if discard:
                logging.info(f"Removing {discard[0]} from discard pile")
                discard.pop(0)

        elif "Ends:" in event_line:
            print(event_line)  # Keeping the print for debugging

    if hand_updated:
        hand.sort()  # Sort only if hand was modified
        logging.info(f"Hand updated and sorted: {hand}")


# data class used to receive data from API POST
class UpdateInfo(BaseModel):
    game_id: str
    event: str

@app.post("/update-2p-game/")
async def update_2p_game(update_info: UpdateInfo):
    '''
        Game Server calls this endpoint to update player on game status and other players' moves.
        Typically only called at the end of game.
    '''
    # TODO - Your code here - update this section if you want
    process_events(update_info.event)
    print(update_info.event)
    return {"status": "OK"}

@app.post("/draw/")
async def draw(update_info: UpdateInfo):
    """Game Server calls this endpoint to start the player's turn with a draw from either the discard pile or the stock."""
    global cannot_discard

    process_events(update_info.event)

    # Use minimax to decide the best move
    _, best_move = minimax(hand, 2, True)  # Depth 2 for quick decision-making

    logging.info(f"Minimax decided to: {best_move}")
    return {"play": best_move}



def get_of_a_kind_count(hand):
    of_a_kind_count = [0, 0, 0, 0]  # how many 1 of a kind, 2 of a kind, etc in our hand
    last_val = hand[0][0]
    count = 0
    for card in hand[1:]:
        cur_val = card[0]
        if cur_val == last_val:
            count += 1
        else:
            of_a_kind_count[count] += 1
            count = 0
        last_val = cur_val
    of_a_kind_count[count] += 1  # Need to get the last card fully processed
    return of_a_kind_count

def get_count(hand, card):
    count = 0
    for check_card in hand:
        if check_card[0] == card[0]: count += 1
    return count

#def test_get_of_a_kind_count():
#    assert get_of_a_kind_count(["2S", "2H", "2D", "7C", "7D", "7S", "7H", "QC", "QD", "QH", "AH"]) == [1, 0, 2, 1]

def minimax(hand, depth, is_maximizing):
    """Minimax function to determine the best discard/meld strategy."""
    if depth == 0 or is_game_over(hand):
        return evaluate_hand(hand)  # Evaluate current hand

    if is_maximizing:
        max_eval = float('-inf')
        for move in get_possible_moves(hand):
            new_hand = simulate_move(hand, move)
            eval = minimax(new_hand, depth - 1, False)
            max_eval = max(max_eval, eval)
        return max_eval
    else:
        min_eval = float('inf')
        for move in get_possible_moves(hand):
            new_hand = simulate_move(hand, move)
            eval = minimax(new_hand, depth - 1, True)
            min_eval = min(min_eval, eval)
        return min_eval

def is_game_over(hand):
    """Determine if the hand is in a terminal (winning) state."""
    return len(hand) == 0  # If all cards are melded, game is over

def evaluate_hand(hand):
    """Heuristic to evaluate a hand (minimize unmeldable cards)."""
    of_a_kind_count = get_of_a_kind_count(hand)
    return -(of_a_kind_count[0] + (of_a_kind_count[1] * 2))  # Fewer unmatched cards is better

def get_possible_moves(hand):
    """Generate all possible discard/meld actions."""
    moves = []
    for card in hand:
        moves.append(("discard", card))  # Discard move
    return moves

def simulate_move(hand, move):
    """Simulate a move (discard/meld) and return the new hand state."""
    new_hand = hand[:]
    if move[0] == "discard":
        new_hand.remove(move[1])  # Remove discarded card
    return new_hand

@app.post("/lay-down/")
async def lay_down(update_info: UpdateInfo):
    """Game server calls this endpoint to conclude the player's turn with melding and/or discarding."""

    global hand, discard, cannot_discard

    process_events(update_info.event)
    
    # Use minimax to determine the best discard move
    best_move = None
    best_eval = float('-inf')
    
    for move in get_possible_moves(hand):
        new_hand = simulate_move(hand, move)
        move_eval = minimax(new_hand, depth=2, is_maximizing=False)  # Search 2 moves ahead

        if move_eval > best_eval:
            best_eval = move_eval
            best_move = move

    # Execute the best move
    if best_move:
        hand.remove(best_move[1])
        return {"play": f"discard {best_move[1]}"}

    return {"play": "noop"}  # No action if no move is found

@app.get("/shutdown")
async def shutdown_API():
    ''' Game Server calls this endpoint to shut down the player's client after testing is completed.  Only used if DEBUG is True. '''
    os.kill(os.getpid(), signal.SIGTERM)
    logging.info("Player client shutting down...")
    return fastapi.Response(status_code=200, content='Server shutting down...')


''' Main code here - registers the player with the server via API call, and then launches the API to receive game information '''
if __name__ == "__main__":

    if (DEBUG):
        url = "http://127.0.0.1:16200/test"

        # TODO - Change logging.basicConfig if you want
        logging.basicConfig(filename="RummyPlayer.log", format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',level=logging.INFO)
    else:
        url = "http://127.0.0.1:16200/register"
        # TODO - Change logging.basicConfig if you want
        logging.basicConfig(filename="RummyPlayer.log", format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',level=logging.WARNING)

    payload = {
        "name": USER_NAME,
        "address": "127.0.0.1",
        "port": str(PORT)
    }

    try:
        # Call the URL to register client with the game server
        response = requests.post(url, json=payload)
    except Exception as e:
        print("Failed to connect to server.  Please contact Mr. Dole.")
        exit(1)

    if response.status_code == 200:
        print("Request succeeded.")
        print("Response:", response.json())  # or response.text
    else:
        print("Request failed with status:", response.status_code)
        print("Response:", response.text)
        exit(1)

    # run the client API using uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)