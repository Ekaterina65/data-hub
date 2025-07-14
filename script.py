import os
import json
import time
import logging
from typing import Dict, Any, Optional

import requests
from web3 import Web3
from web3.contract import Contract
from web3.types import LogReceipt
from dotenv import load_dotenv

# --- Configuration & Setup ---

load_dotenv()

# Configure logging to provide detailed output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Constants ---
# In a real application, this ABI would be loaded from a file.
# This is a simplified ABI for a generic bridge contract's lock event.
BRIDGE_CONTRACT_ABI = json.loads('''
[
    {
        "anonymous": false,
        "inputs": [
            {
                "indexed": true,
                "internalType": "address",
                "name": "sender",
                "type": "address"
            },
            {
                "indexed": true,
                "internalType": "address",
                "name": "recipient",
                "type": "address"
            },
            {
                "indexed": false,
                "internalType": "uint256",
                "name": "amount",
                "type": "uint256"
            },
            {
                "indexed": false,
                "internalType": "uint256",
                "name": "destinationChainId",
                "type": "uint256"
            },
            {
                "indexed": false,
                "internalType": "bytes32",
                "name": "transactionHash",
                "type": "bytes32"
            }
        ],
        "name": "TokensLocked",
        "type": "event"
    }
]
''')

STATE_FILE = 'processed_events_state.json'

class StateDB:
    """
    Manages the state of processed events to prevent re-processing.
    Persists state to a local JSON file.
    """
    def __init__(self, state_file_path: str):
        """
        Initializes the StateDB.

        Args:
            state_file_path (str): The path to the JSON file for state persistence.
        """
        self.state_file_path = state_file_path
        self.processed_events = self._load_state()
        logger.info(f"StateDB initialized. Loaded {len(self.processed_events)} processed events from {self.state_file_path}.")

    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        """
        Loads the state from the JSON file.
        Returns an empty dictionary if the file doesn't exist.
        """
        try:
            with open(self.state_file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"State file not found at {self.state_file_path}. Starting with an empty state.")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.state_file_path}. Starting with an empty state.")
            return {}

    def _save_state(self):
        """
        Saves the current state to the JSON file.
        """
        try:
            with open(self.state_file_path, 'w') as f:
                json.dump(self.processed_events, f, indent=4)
        except IOError as e:
            logger.error(f"Failed to save state to {self.state_file_path}: {e}")

    def is_event_processed(self, event_signature: str) -> bool:
        """
        Checks if an event has already been processed.

        Args:
            event_signature (str): A unique identifier for the event (e.g., transaction hash + log index).

        Returns:
            bool: True if the event has been processed, False otherwise.
        """
        return event_signature in self.processed_events

    def mark_event_as_processed(self, event_signature: str, event_data: Dict[str, Any]):
        """
        Marks an event as processed and saves the state.

        Args:
            event_signature (str): The unique identifier for the event.
            event_data (Dict[str, Any]): The data associated with the event.
        """
        self.processed_events[event_signature] = {
            'data': event_data,
            'processed_at': time.time()
        }
        self._save_state()
        logger.info(f"Event {event_signature} marked as processed.")

class BlockchainConnector:
    """
    Handles the connection to a blockchain node via Web3.py.
    """
    def __init__(self, rpc_url: str):
        """
        Initializes the connector with an RPC URL.

        Args:
            rpc_url (str): The HTTP or WebSocket URL of the blockchain node.
        """
        self.rpc_url = rpc_url
        self.web3: Optional[Web3] = None

    def connect(self) -> bool:
        """
        Establishes a connection to the blockchain node.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            self.web3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if self.web3.is_connected():
                logger.info(f"Successfully connected to blockchain node at {self.rpc_url}")
                return True
            else:
                logger.error(f"Failed to connect to blockchain node at {self.rpc_url}")
                return False
        except Exception as e:
            logger.error(f"Exception while connecting to {self.rpc_url}: {e}")
            return False

    def get_contract(self, address: str, abi: Dict) -> Optional[Contract]:
        """
        Gets a Web3 contract instance.

        Args:
            address (str): The contract's address.
            abi (Dict): The contract's ABI.

        Returns:
            Optional[Contract]: A Web3 contract instance, or None if not connected.
        """
        if not self.web3 or not self.web3.is_connected():
            logger.error("Cannot get contract, not connected to blockchain.")
            return None
        checksum_address = self.web3.to_checksum_address(address)
        return self.web3.eth.contract(address=checksum_address, abi=abi)

    def get_latest_block_number(self) -> Optional[int]:
        """
        Retrieves the latest block number.

        Returns:
            Optional[int]: The latest block number, or None on failure.
        """
        if not self.web3 or not self.web3.is_connected():
            logger.error("Cannot get block number, not connected to blockchain.")
            return None
        try:
            return self.web3.eth.block_number
        except Exception as e:
            logger.error(f"Error getting latest block number: {e}")
            return None

class RelayerService:
    """
    Simulates relaying a transaction to a destination chain by calling an API endpoint.
    """
    def __init__(self, api_endpoint: str):
        """
        Initializes the relayer service.

        Args:
            api_endpoint (str): The API endpoint to which the event data will be POSTed.
        """
        self.api_endpoint = api_endpoint

    def relay_transaction(self, event_data: Dict[str, Any]) -> bool:
        """
        Sends event data to the configured API endpoint.

        Args:
            event_data (Dict[str, Any]): The processed event data to be relayed.

        Returns:
            bool: True if the API call was successful (2xx status), False otherwise.
        """
        headers = {'Content-Type': 'application/json'}
        payload = {
            'eventType': 'TokensLocked',
            'payload': event_data
        }
        logger.info(f"Relaying transaction to {self.api_endpoint} with payload: {payload}")
        try:
            response = requests.post(self.api_endpoint, json=payload, headers=headers, timeout=10)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            logger.info(f"Successfully relayed transaction. API response: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to relay transaction via API: {e}")
            return False

class EventProcessor:
    """
    Processes events fetched by the EventListener.
    """
    def __init__(self, state_db: StateDB, relayer: RelayerService):
        """
        Initializes the processor.

        Args:
            state_db (StateDB): The state management instance.
            relayer (RelayerService): The service for relaying actions to the destination.
        """
        self.state_db = state_db
        self.relayer = relayer

    def process_event(self, event: LogReceipt):
        """
        Processes a single blockchain event log.
        It checks for duplicates, formats the data, and triggers the relayer.

        Args:
            event (LogReceipt): The raw event log from Web3.py.
        """
        # Create a unique signature for the event to prevent re-processing
        tx_hash = event['transactionHash'].hex()
        log_index = event['logIndex']
        event_signature = f"{tx_hash}-{log_index}"

        if self.state_db.is_event_processed(event_signature):
            logger.debug(f"Skipping already processed event: {event_signature}")
            return

        logger.info(f"Processing new TokensLocked event: {event_signature}")

        # Format event data for relaying
        event_args = event['args']
        processed_data = {
            'source_transaction_hash': tx_hash,
            'sender': event_args['sender'],
            'recipient': event_args['recipient'],
            'amount': event_args['amount'],
            'destination_chain_id': event_args['destinationChainId']
        }

        # Attempt to relay the transaction
        if self.relayer.relay_transaction(processed_data):
            # If relaying is successful, mark the event as processed
            self.state_db.mark_event_as_processed(event_signature, processed_data)
        else:
            logger.warning(f"Relaying failed for event {event_signature}. It will be retried in the next poll.")

class EventListener:
    """
    The core component that listens for new blocks and filters for specific events.
    """
    def __init__(self, connector: BlockchainConnector, contract: Contract, processor: EventProcessor, start_block: int):
        self.connector = connector
        self.contract = contract
        self.processor = processor
        self.current_block = start_block
        self.poll_interval = 15  # seconds
        self.reorg_confirmation_depth = 5 # blocks

    def start(self):
        """
        Starts the main event listening loop.
        """
        logger.info(f"Starting event listener for contract {self.contract.address} from block {self.current_block}")
        while True:
            try:
                latest_block = self.connector.get_latest_block_number()
                if latest_block is None:
                    logger.warning("Could not fetch latest block number. Retrying...")
                    time.sleep(self.poll_interval)
                    continue
                
                # To handle reorgs, we only process blocks that are a few blocks old.
                target_block = latest_block - self.reorg_confirmation_depth

                if self.current_block > target_block:
                    logger.info(f"Waiting for more blocks to be confirmed. Current: {self.current_block}, Target: {target_block}")
                    time.sleep(self.poll_interval)
                    continue

                logger.info(f"Scanning for events from block {self.current_block} to {target_block}")

                event_filter = self.contract.events.TokensLocked.create_filter(
                    fromBlock=self.current_block,
                    toBlock=target_block
                )
                events = event_filter.get_all_entries()

                if events:
                    logger.info(f"Found {len(events)} new TokensLocked event(s).")
                    for event in events:
                        self.processor.process_event(event)
                else:
                    logger.info("No new events found in this range.")

                # Update the current block to continue from where we left off
                self.current_block = target_block + 1

            except Exception as e:
                logger.error(f"An error occurred in the listening loop: {e}")
                # In case of a major error, wait longer before retrying
                time.sleep(self.poll_interval * 2)

            time.sleep(self.poll_interval)

def main():
    """
    Main function to orchestrate the listener setup and execution.
    """
    # --- Load Configuration from .env file ---
    source_rpc_url = os.getenv("SOURCE_RPC_URL")
    bridge_contract_address = os.getenv("BRIDGE_CONTRACT_ADDRESS")
    relayer_api_endpoint = os.getenv("RELAYER_API_ENDPOINT")
    start_block_str = os.getenv("START_BLOCK", "latest")

    if not all([source_rpc_url, bridge_contract_address, relayer_api_endpoint]):
        logger.critical("Missing critical environment variables: SOURCE_RPC_URL, BRIDGE_CONTRACT_ADDRESS, RELAYER_API_ENDPOINT")
        return

    # --- Initialize Components ---
    logger.info("--- Initializing Cross-Chain Bridge Listener ---")
    
    # 1. State Database
    state_db = StateDB(STATE_FILE)

    # 2. Blockchain Connector
    connector = BlockchainConnector(source_rpc_url)
    if not connector.connect():
        logger.critical("Failed to connect to blockchain. Exiting.")
        return

    # 3. Contract Instance
    contract = connector.get_contract(bridge_contract_address, BRIDGE_CONTRACT_ABI)
    if not contract:
        logger.critical("Failed to initialize contract instance. Exiting.")
        return

    # 4. Relayer and Processor
    relayer = RelayerService(api_endpoint=relayer_api_endpoint)
    processor = EventProcessor(state_db=state_db, relayer=relayer)

    # 5. Event Listener
    if start_block_str.lower() == 'latest':
        start_block = connector.get_latest_block_number()
        if start_block is None:
            logger.critical("Could not determine latest block. Please set START_BLOCK manually. Exiting.")
            return
    else:
        try:
            start_block = int(start_block_str)
        except ValueError:
            logger.critical(f"Invalid START_BLOCK value: {start_block_str}. Must be an integer or 'latest'.")
            return

    listener = EventListener(
        connector=connector,
        contract=contract,
        processor=processor,
        start_block=start_block
    )

    # --- Start the service ---
    try:
        listener.start()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Exiting gracefully.")
    except Exception as e:
        logger.critical(f"An unhandled exception occurred: {e}", exc_info=True)

if __name__ == '__main__':
    main()
