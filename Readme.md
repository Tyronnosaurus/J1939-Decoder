The main script (PrepareMF4.py) does the following:

1. Parse logs from a Nexic CAN sniffer and extract the 19 bytes containing frame data in a proprietary format.
2. Parse these 19 bytes for relevant data for the CAN J1939 frame (Priority, PGN, Payload, etc).
3. Build the extended CAN ID.
4. Export all info to a CSV file (for debugging visually in case of parsing bugs).
5. Export relevant info to an MF4 file (for loading into asammdf and extracting signals using a DBC dictionary).

The 'Originals' folder contains an example of a log taken from the CAN sniffer.
The 'Results' folder contains the corresponding CSV and MF4 generated from the log.


At the moment, the generated MF4 file is not 100% usable. asammdf does not seem to recognize the ID column as actual IDs when trying to export signals with a DBC dictionary. It reports that "0 of 0 IDs" were found. More info in [this Stack Overflow thread](https://stackoverflow.com/questions/74522618/asammdf-gui-not-recognizing-id-column-as-ids-for-can-j1939-ids).