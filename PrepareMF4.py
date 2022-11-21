from pathlib import Path
import os
import re
import pandas as pd
import numpy as np
import struct
from asammdf import MDF, Signal
from asammdf.blocks.source_utils import Source
from typing import List


"""
This script does the following:
    1) Parse logs from a Nexic CAN sniffer and extract the part that contains data about the CAN frames.
    2) Parse the CAN frames, which use J1939 protocol, for relevant data (Priority, PGN, Payload, etc).
    3) Build the extended CAN ID.
    4) Export all info to a CSV file (for debugging visually in case of parsing bugs).
    5) Export relevant info to an MF4 file (for loading into asammdf and extracting signals using a DBC dictionary).
"""

sourcePath = r"Originals\ExampleLog.log"


# Create results folder if it doesn't exist
ResultsFolder = "Results"
if not os.path.exists(ResultsFolder): os.makedirs(ResultsFolder)


# As we parse stuff, we'll store it in a dataframe. We can then export all columns to a CSV (for visual debugging) and some columns to an MF4.
df = pd.DataFrame(columns=['Original', 'LogTimestamp', 'LogID', 'Ret', 'Sz', 'Blk', 'LogDataBytes', 'timestamps', 'echoByte', 'PGN', 'Priority', 'Source', 'Destination', 'DataBytes', 'DataLength', 'ID', 'BusChannel', 'IDE', 'DLC', 'Dir', 'EDL', 'BRS', 'PgnLabel', 'PgnInDbc'])

# Load PGN label table to match PGNs with human readable names. Taken from CSS Electronics (https://www.csselectronics.com/pages/j1939-pgn-conversion-tool  -> PGN list tab)
pgn_df = pd.read_csv("PGN list.csv", sep=';')



def main():

    with open(sourcePath, "r") as f_original:
        
        lines = f_original.readlines()

        i = 0   # Line counter. Do NOT use an index with enumerate(), since there are lines we want to skip. Only increase i when we actually add a row to df

        for line in lines:
            
            if ("Data:" not in line): continue   # Exit clause: Skip line if it has no data

            df.at[i,'Original'] = line.strip() # Store the whole original line so that it is included in the CSV. This makes it easier to debug visually for parsing errors. 


            ################################
            #### Parse log entry values ####
            ################################
            """ We sniffed data using a Nexiq CAN sniffer. The application Device Tester software (v3.1.0.6) has a logging feature that we used to record the data.
                The resulting log is not the actual CAN frame, but rather a proprietary format that includes the CAN frame plus extra info.
            
                Example of a line in the CAN sniffer's log:
                000001.226604 (000.003827)  Rx() ID = 00 Ret = 0019 Sz = 02048 Blk = 1 Data:  00 11 EE B0 00 20 FF 00 03 00 FF 10 21 00 00 00 FF D0 FF
                    The actual data about the CAN packet is encoded in those last 19 hex bytes. 
                    This ID is unrelated to the CAN ID, so we'll name it differently (LogID) to avoid confusion.
                    We also parse Ret, Sz and Blk, although as far as I know we won't need them.
            """

            # Get log entry timestamp
            df.at[i,'LogTimestamp'] = re.search(r"^(.*) \(" , line).group(1)
            
            # Get log info: ID, Ret, Sz, Blk (no idea what they are, also this ID is completely unrelated to the CAN frame's ID)
            df.at[i,'LogID'] = re.search("ID = ([0-9]*)" , line).group(1)
            df.at[i,'Ret']   = re.search("Ret = ([0-9]*)" , line).group(1)
            df.at[i,'Sz']    = re.search("Sz = ([0-9]*)" , line).group(1)

            blk = re.search("Blk = ([0-9]*)" , line)    # Some lines don't have a blk, hence we need an 'if'
            if (blk): df.at[i,'Blk'] = blk.group(1)

            # Get log entry data bytes (typically 19 bytes, the actual CAN frame is included here in a proprietary format)
            dataBytes_hex = re.search("Data: ([0-9A-F ]*)" , line).group(1) # Get data as " 00 11 EE B0 00 20 FF 00 03 00 FF 10 21 00 00 00 FF D0 FF " 
            dataLength = len(re.findall("( [0-9A-F]{2})", dataBytes_hex))   # Count how many groups of two chars we have
            dataBytes_hex = dataBytes_hex.replace(" ","") # Remove spaces: "0011EEB00020FF000300FF1021000000FFD0FF"
            df.at[i,'LogDataBytes'] = dataBytes_hex

            if (dataLength<19): continue    # Exit clause: Skip lines with anormally short DataBytes


            #################################
            #### Parse CAN (J1939) frame ####
            #################################
            # The Nexiq CAN reader presents the DataBytes in a proprietary format.
            # The following decoding is based on documentation from Nexiq's technical support.
            # (Recommended Practice, Proposed RP 1210C; RP1210C-FINAL.pdf, page 39, section 15.5: The J1939 Message from RP1210_ReadMessage)
            timestamp_hex   = dataBytes_hex[0:8]
            echoByte_hex    = dataBytes_hex[8:10]
            pgn_hex         = dataBytes_hex[14:16] + dataBytes_hex[12:14] + dataBytes_hex[10:12]    # PGN given in little endian. Must reverse the bytes: 20 F3 00 -> 00 F3 20
            priority_hex    = dataBytes_hex[16:18]
            source_hex      = dataBytes_hex[18:20]
            destination_hex = dataBytes_hex[20:22]
            payload_hex     = dataBytes_hex[22:38]


            df.at[i,'timestamps']  = struct.unpack('!f', bytes.fromhex(timestamp_hex))[0]   # Convert hex to float   
            df.at[i,'echoByte']    = echoByte_hex
            df.at[i,'PGN']         = pgn_hex
            df.at[i,'Priority']    = priority_hex
            df.at[i,'Source']      = source_hex
            df.at[i,'Destination'] = destination_hex
            df.at[i,'DataBytes']   = payload_hex
            df.at[i,'DataLength']  = len(payload_hex)//2    # Count pairs of characters in the payload. 2 hexadecimal characters are 1 byte


            # Build the 29 bit Extended CAN ID:
            #                  Extended Data Page
            #       Priority     (AKA Reserved)     Data Page   PDU Format   PDU specific   Source Address
            #       (3 bits)       (1 bits)          (1 bits)    (8 bits)      (8 bits)       (8 bits)
            #                 |------------------- PGN (18 bits) ------------------------|

            b1 = hexStr2binStr(priority_hex, 3) # Priority, 3 bits
            b2 = hexStr2binStr(pgn_hex, 18)     # PGN, 18 bits
            b3 = hexStr2binStr(source_hex, 8)   # Source, 8 bits
            ID = b1 + b2 + b3                      # Concatenate binary strings
            #print(b1, b2, b3, " --->  ID", ID, "  Length: ", len(ID), " bits")
            df.at[i,'ID'] = binStr2HexStr(ID)      # Convert back to hexadecimal (ex: "CFF2303")


            # Other boilerplate columns. Taken from the demo.py script. Don't know how necessary they are for asammdf but I include them just in case
            df.at[i,'BusChannel'] = 1
            df.at[i,'IDE'] = 1
            df.at[i,'DLC'] = 1
            df.at[i,'Dir'] = 1
            df.at[i,'EDL'] = 1
            df.at[i,'BRS'] = 1


            # Lookup CSS Electronics' PGN table to get a human readable name for the PGN (e.g. "Electronic Brake Controller 1"),
            # plus a note on whether or not the frame can be decoded with CSS' paid DBC dictionary (https://www.csselectronics.com/products/j1939-dbc-file)
            pgn_dec = int(pgn_hex, 16)     # Get PGN in decimal

            pgn_label_row = pgn_df[pgn_df["PGN"] == pgn_dec]  # Find subset of rows with matching PGN
            if (not pgn_label_row.empty):                       # If we found a match
                df.at[i,'PgnLabel'] = pgn_label_row.iloc[0]["PGN label"]                  # And get the first row in the subset, second column
                df.at[i,'PgnInDbc'] = pgn_label_row.iloc[0]["In CSS electronics' DBC?"]   # And get the first row in the subset, third column



            i += 1  # If we hit any exit clause, this index won't get increased, so the unfinished row will get overwritten on the next iteration




    ####################################
    ## Prepare the CSV file
    ####################################
    # This is mostly for visual debugging in case there's a parsing error
    # Warning: Excel formats some cells incorrectly (e.g. hexadecimal 30000003 gets interpreted as a decimal).
    #          Open the CSV as text or with some dumb CSV viewer that doesn't try to infer formats.
    filename = Path(sourcePath).stem + ".csv"
    pathResultCsv = os.path.join(ResultsFolder, filename)

    df.to_csv(pathResultCsv, sep=";", index=False)




    ####################################
    ## Prepare the MF4 file
    ####################################
    # Based on the demo.py script that creates a dummy MF4 (copied from https://stackoverflow.com/questions/66630991/create-mf4-to-be-decode-by-j1939-dbc-asammdf).
    # Doing it like this is the only way I've found to have an MF4 file that can be loaded into asammdf AND have the Bus Logging tab active.
    # The Bus Logging tab is where we load a DBC dictionary to extract signals.

    timestampsList = df['timestamps'].tolist()

    samples = []

    samples.append( np.array(df['BusChannel'].values, dtype=np.uint32) ) # BusChannel

    aux = np.array(df['ID'].apply(int, base=16).values) # Convert whole column from hex string to int, and then convert df column to Numpy array
    samples.append(aux)#, dtype=np.uint64) ) # ID

    samples.append( np.array(df['IDE'].values, dtype=np.uint32) ) # IDE
    samples.append( np.array(df['DLC'].values, dtype=np.uint32) ) # DLC
    samples.append( np.array(df['DataLength'].values, dtype=np.uint32) ) # DataLength
    samples.append( np.array(df['Dir'].values, dtype=np.uint32) ) # Dir
    samples.append( np.array(df['EDL'].values, dtype=np.uint32) ) # EDL
    samples.append( np.array(df['BRS'].values, dtype=np.uint32) ) # BRS

    auxCol = ColumnHexToListOfInts(df['DataBytes'])
    auxNpArray = np.array(auxCol)#, dtype=np.dtype('(8,)u1') )
    samples.append( auxNpArray ) # DataBytes



    types = [('CAN_DataFrame.BusChannel', 'u1'),
             ('CAN_DataFrame.ID', 'u4'),
             ('CAN_DataFrame.IDE', 'u1'),
             ('CAN_DataFrame.DLC', 'u1'),
             ('CAN_DataFrame.DataLength', 'u1'),
             ('CAN_DataFrame.Dir', 'u1'),
             ('CAN_DataFrame.EDL', 'u1'),
             ('CAN_DataFrame.BRS', 'u1'),
             ('CAN_DataFrame.DataBytes', 'u1', (8,)),
            ]


    # Prepare signals object
    sigs = []

    sig = Signal(
        samples = np.core.records.fromarrays(arrayList=samples, dtype=np.dtype(types)),

        timestamps = timestampsList,
        
        name='Channel_structure_composition',
        comment='Structure channel composition',
        source=Source(
            source_type = Source.SOURCE_BUS,
            bus_type    = Source.BUS_TYPE_CAN,
            name        = "CAN bus",
            path        = "CAN bus",
            comment     = "",
        )
    )
    sigs.append(sig)


    #Create MF4 object and save data in it
    mdf = MDF(version='4.10')
    mdf.append(sigs, comment='arrays', common_timebase=True)

    filename = Path(sourcePath).stem + ".mf4"
    pathResultMf4 = os.path.join(ResultsFolder, filename)
    mdf.save(pathResultMf4, overwrite=True)

    #print( mdf.get_group(0) )





########################
## Auxiliar functions ##
########################

#Convert hex string to binary string (and pad the binary string with zeroes to the left to a defined length)
def hexStr2binStr(hexStr:str, numBits:int) -> str:
    return (bin(int(hexStr, 16))[2:].zfill(numBits) )


# Convert binary string to hex string
def binStr2HexStr(binStr: str) -> str:
    return( "{0:0>4X}".format(int(binStr, 2)) )


# Convert hex string to list of ints
def HexStrToListOfInts(hexStr) -> List[int]:
    hexs = [hexStr[i:i+2] for i in range(0, len(hexStr), 2)]    # Separate hex: "A123EE"  ->  ["A1", "23", "EE"]
    listOfInts = [int(x, 16) for x in hexs]                     # Convert hex list to int list
    return(listOfInts)


# Converts a whole dataframe's column from Hex strings to a list of ints
def ColumnHexToListOfInts(df_col):
    res = []
    for item in df_col:
        ints = HexStrToListOfInts(item)
        res.append(ints)
        
    return(res)  




main()