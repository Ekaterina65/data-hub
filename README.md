# Data-Hub: Cross-Chain Bridge Event Listener

This project is a simulation of a critical component in a cross-chain bridge system: an off-chain event listener and relayer. It is designed to monitor a `TokensLocked` event on a source blockchain, process it, and relay the information to a destination chain's endpoint.

This script serves as an architectural blueprint for building robust, fault-tolerant off-chain services for decentralized applications.

## Concept

In many cross-chain bridge designs (like lock-and-mint), the process works as follows:

1.  **Lock**: A user locks tokens on the source chain by calling a function on a bridge smart contract.
2.  **Event Emission**: The smart contract emits an event (e.g., `TokensLocked`) containing details like the recipient's address, the amount, and the destination chain ID.
3.  **Listening**: Off-chain services, often called relayers or oracles, listen for these specific events on the source chain.
4.  **Verification & Relaying**: Once an event is detected and confirmed, the relayer submits a signed message or transaction to the destination chain.
5.  **Mint**: A contract on the destination chain verifies the relayer's message and mints an equivalent amount of wrapped tokens for the recipient.

This script simulates steps 3 and 4. It acts as the relayer, listening for `TokensLocked` events and making a simulated API call to a destination endpoint, which would represent the entry point for step 5.

## Code Architecture

The architecture is modular, with each class having a distinct responsibility. This separation of concerns makes the system easier to test, maintain, and extend.

```
+-----------------------+      +---------------------+      +-----------------+
|    Source Chain       |----->| BlockchainConnector |----->|  EventListener  |
| (e.g., Ethereum Node) |      | (Web3.py Wrapper)   |      | (Polling Loop)  |
+-----------------------+      +---------------------+      +--------+--------+
                                                                     |
                                                                     v
                                                            +--------+---------+
                                                            | EventProcessor  |
                                                            | (Business Logic)|
                                                            +--------+---------+
                                                                     |
                                                                     |
           +---------------------------------------------------------+--------------------------------------------------------+
           |                                                         |                                                        |
           v                                                         v                                                        |
  +--------+--------+                                       +--------+--------+                                       +--------+--------+
  |     StateDB     |                                       | RelayerService  |                                       |    Logging      |
  |  (Persistence)  |                                       | (API Caller)    |                                       | (Monitoring)    |
  +-----------------+                                       +--------+--------+                                       +-----------------+
                                                                     |
                                                                     v
                                                            +------------------------+
                                                            | Destination Endpoint   |
                                                            | (Mock API)             |
                                                            +------------------------+
```

### Components

*   `BlockchainConnector`: A wrapper around `Web3.py` that manages the connection to the source chain's RPC endpoint. It provides helper methods for getting blocks and contract instances.
*   `EventListener`: The core of the service. It runs an infinite loop, periodically polling the blockchain for new blocks. It filters for `TokensLocked` events within a specified block range and passes them to the `EventProcessor`.
*   `EventProcessor`: Contains the business logic. It takes a raw event, checks if it has already been processed (using `StateDB`), formats the data, and instructs the `RelayerService` to perform the cross-chain action.
*   `RelayerService`: Simulates the final step of relaying information. It takes the processed event data and makes a POST request to a configured API endpoint. In a real-world scenario, this component would be responsible for signing and sending a transaction to the destination chain.
*   `StateDB`: A simple, file-based persistence layer. It keeps a record of processed event signatures (a combination of transaction hash and log index) in a JSON file to ensure that events are not processed more than once, even if the service restarts.

## How it Works

1.  **Initialization**: The `main` function loads configuration from a `.env` file, including RPC URLs, contract addresses, and API endpoints.
2.  **Component Setup**: It initializes all the architectural components: `StateDB`, `BlockchainConnector`, `RelayerService`, `EventProcessor`, and finally the `EventListener`.
3.  **Polling Loop**: The `EventListener.start()` method begins the main loop.
4.  **Block Fetching**: In each iteration, it fetches the latest block number from the source chain.
5.  **Reorg Protection**: To avoid processing events on unstable blocks, it only scans up to `latest_block - REORG_CONFIRMATION_DEPTH`. This ensures that the blocks being processed are unlikely to be part of a chain reorganization.
6.  **Event Filtering**: It uses `web3.eth.filter` to efficiently query for `TokensLocked` events between the `last_processed_block` and the `target_block`.
7.  **Processing**: For each event found, the `EventProcessor` is invoked.
8.  **Duplicate Check**: The processor first creates a unique signature for the event and checks with `StateDB` if it has been handled before. If so, it skips the event.
9.  **Relaying Action**: If the event is new, the `RelayerService` is called to send the data to the destination API.
10. **State Update**: If the relay was successful, `StateDB` is updated to mark the event as processed, and the state is saved to `processed_events_state.json`.
11. **Loop Continuation**: The `last_processed_block` is updated, and the listener sleeps for a configured interval before starting the next iteration.

## Usage Example

### 1. Prerequisites

*   Python 3.8+
*   An RPC endpoint URL for an Ethereum-compatible blockchain (e.g., from Infura, Alchemy, or a local node).

### 2. Installation

Clone the repository and install the required dependencies:

```bash
git clone https://github.com/your-username/data-hub.git
cd data-hub
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the root of the project and populate it with your configuration. You can use any contract that emits an event with a similar signature for testing.

```env
# .env file

# RPC endpoint for the source blockchain (e.g., Sepolia testnet)
SOURCE_RPC_URL="https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID"

# Address of the bridge smart contract to monitor on the source chain
BRIDGE_CONTRACT_ADDRESS="0x1234567890123456789012345678901234567890"

# A mock API endpoint to receive the relayed data. You can use a service like Pipedream or Webhook.site to create one for testing.
RELAYER_API_ENDPOINT="https://webhook.site/your-unique-url"

# The block number to start scanning from. Use 'latest' to start from the current head of the chain.
START_BLOCK="latest"
```

### 4. Running the Script

Execute the script from your terminal:

```bash
python script.py
```

The service will start, connect to the blockchain, and begin polling for events.

### Example Log Output

```
2023-10-27 14:30:00 - __main__ - INFO - --- Initializing Cross-Chain Bridge Listener ---
2023-10-27 14:30:00 - __main__ - INFO - StateDB initialized. Loaded 0 processed events from processed_events_state.json.
2023-10-27 14:30:01 - __main__ - INFO - Successfully connected to blockchain node at https://sepolia.infura.io/v3/...
2023-10-27 14:30:02 - __main__ - INFO - Starting event listener for contract 0x123456... from block 4850123
2023-10-27 14:30:02 - __main__ - INFO - Scanning for events from block 4850123 to 4850130
2023-10-27 14:30:04 - __main__ - INFO - No new events found in this range.
2023-10-27 14:30:19 - __main__ - INFO - Scanning for events from block 4850131 to 4850135
2023-10-27 14:30:21 - __main__ - INFO - Found 1 new TokensLocked event(s).
2023-10-27 14:30:21 - __main__ - INFO - Processing new TokensLocked event: 0xabcdef...-0
2023-10-27 14:30:21 - __main__ - INFO - Relaying transaction to https://webhook.site/... with payload: {...}
2023-10-27 14:30:22 - __main__ - INFO - Successfully relayed transaction. API response: {"status": "ok"}
2023-10-27 14:30:22 - __main__ - INFO - Event 0xabcdef...-0 marked as processed.
```
